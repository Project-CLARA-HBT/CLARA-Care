from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_source_hub_sync_davidrug_uses_structured_api(monkeypatch) -> None:
    token = _login("alice@research.clara")

    def _fake_http_post_json(url: str, *, payload: dict[str, object]) -> dict[str, object]:
        assert url.endswith("/api/services/app/soDangKy/GetAllPublicServerPaging")
        assert payload["filterText"] == "panadol"
        assert payload["KichHoat"] is True
        return {
            "result": {
                "totalCount": 1,
                "items": [
                    {
                        "id": 55750,
                        "tenThuoc": "Panadol Extra",
                        "soDangKy": "539100184523",
                        "thongTinThuocCoBan": {
                            "hoatChatChinh": "Paracetamol, Caffeine",
                            "dangBaoChe": "Viên nén",
                            "hamLuong": "500mg + 65mg",
                        },
                        "congTyDangKy": {
                            "tenCongTyDangKy": "Công ty TNHH GlaxoSmithKline",
                        },
                        "thongTinDangKyThuoc": {
                            "ngayCapSoDangKy": "2023-07-14T00:00:00+07:00",
                        },
                    }
                ],
            }
        }

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._http_post_json",
        _fake_http_post_json,
    )

    sync_response = client.post(
        "/api/v1/research/source-hub/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "davidrug", "query": "panadol", "limit": 5},
    )
    assert sync_response.status_code == 200
    payload = sync_response.json()
    assert payload["source"] == "davidrug"
    assert payload["fetched"] == 1
    assert len(payload["records"]) == 1
    record = payload["records"][0]
    assert record["id"] == "davidrug:55750"
    assert record["title"] == "Panadol Extra"
    assert record["metadata"]["so_dang_ky"] == "539100184523"
    assert "Paracetamol" in (record["snippet"] or "")

    list_response = client.get(
        "/api/v1/research/source-hub/records",
        headers={"Authorization": f"Bearer {token}"},
        params={"source": "davidrug"},
    )
    assert list_response.status_code == 200
    rows = list_response.json()["records"]
    assert len(rows) >= 1
    assert rows[0]["source"] == "davidrug"


def test_source_hub_sync_davidrug_returns_warning_when_empty(monkeypatch) -> None:
    token = _login("alice@research.clara")

    def _fake_http_post_json(_url: str, *, payload: dict[str, object]) -> dict[str, object]:
        assert payload["filterText"] == "does-not-exist"
        return {"result": {"totalCount": 0, "items": []}}

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._http_post_json",
        _fake_http_post_json,
    )

    response = client.post(
        "/api/v1/research/source-hub/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "davidrug", "query": "does-not-exist", "limit": 3},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["fetched"] == 0
    assert payload["warnings"]
    assert "không có kết quả" in payload["warnings"][0].lower()


def test_source_hub_sync_semantic_scholar_records(monkeypatch) -> None:
    token = _login("alice@research.clara")

    def _fake_http_get_json(
        url: str, *, params: dict[str, object] | None = None
    ) -> dict[str, object]:
        assert url.endswith("/graph/v1/paper/search")
        assert params is not None
        assert params["query"] == "warfarin nsaid"
        return {
            "data": [
                {
                    "paperId": "abc123",
                    "title": "Warfarin and NSAID interaction risk",
                    "year": 2024,
                    "url": "https://www.semanticscholar.org/paper/abc123",
                    "venue": "Journal of Clinical Pharmacology",
                    "journal": {"name": "J Clin Pharmacol"},
                }
            ]
        }

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._http_get_json",
        _fake_http_get_json,
    )

    response = client.post(
        "/api/v1/research/source-hub/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "semantic_scholar", "query": "warfarin nsaid", "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "semantic_scholar"
    assert body["fetched"] == 1
    assert body["records"][0]["id"] == "semantic_scholar:abc123"
    assert "Warfarin" in body["records"][0]["title"]


def test_source_hub_sync_dailymed_records(monkeypatch) -> None:
    token = _login("alice@research.clara")

    def _fake_http_get_json(
        url: str, *, params: dict[str, object] | None = None
    ) -> dict[str, object]:
        assert "dailymed/services/v1/drugname/warfarin/spls.json" in url
        assert params is None
        return {
            "data": [
                [
                    "f4f2f5f4-bdc1-4314-b9f5-0ce62d032e44",
                    "Warfarin Sodium",
                    "3",
                    "2024-11-01",
                ]
            ]
        }

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._http_get_json",
        _fake_http_get_json,
    )

    response = client.post(
        "/api/v1/research/source-hub/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "dailymed", "query": "warfarin", "limit": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "dailymed"
    assert payload["fetched"] == 1
    record = payload["records"][0]
    assert record["id"].startswith("dailymed:")
    assert record["title"] == "Warfarin Sodium"
    assert "dailymed" in (record["url"] or "").lower()


def test_source_hub_sync_clinicaltrials_records(monkeypatch) -> None:
    token = _login("alice@research.clara")

    def _fake_http_get_json(
        url: str, *, params: dict[str, object] | None = None
    ) -> dict[str, object]:
        assert url.endswith("/api/v2/studies")
        assert isinstance(params, dict)
        assert params.get("query.term") == "warfarin interaction"
        return {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT12345678",
                            "briefTitle": "Warfarin and NSAID interaction study",
                        },
                        "statusModule": {
                            "overallStatus": "RECRUITING",
                            "startDateStruct": {"date": "2025-03-01"},
                        },
                    }
                }
            ]
        }

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._http_get_json",
        _fake_http_get_json,
    )

    response = client.post(
        "/api/v1/research/source-hub/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "clinicaltrials", "query": "warfarin interaction", "limit": 3},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "clinicaltrials"
    assert payload["fetched"] == 1
    record = payload["records"][0]
    assert record["external_id"] == "NCT12345678"
    assert record["title"] == "Warfarin and NSAID interaction study"
    assert "clinicaltrials.gov/study/NCT12345678" in (record["url"] or "")


def test_source_hub_sync_vn_moh_html_crawl_filters_and_dedupes(monkeypatch) -> None:
    token = _login("alice@research.clara")

    html_doc = """
    <html>
      <body>
        <a href="/tin-tuc/huong-dan-dieu-tri-sot-xuat-huyet-2025.html">
          Hướng dẫn điều trị sốt xuất huyết 2025
        </a>
        <a href="/tin-tuc/huong-dan-dieu-tri-sot-xuat-huyet-2025.html">Bản sao link trùng</a>
        <a href="/tin-tuc/ke-hoach-tiem-chung.html">Kế hoạch tiêm chủng mở rộng</a>
      </body>
    </html>
    """

    def _fake_http_get_text(url: str, *, params: dict[str, object] | None = None) -> str:
        assert "moh.gov.vn" in url
        assert params is None
        return html_doc

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._http_get_text",
        _fake_http_get_text,
    )

    response = client.post(
        "/api/v1/research/source-hub/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "vn_moh", "query": "sot xuat huyet", "limit": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "vn_moh"
    assert payload["fetched"] == 1
    assert len(payload["records"]) == 1
    record = payload["records"][0]
    assert record["id"].startswith("vn_moh:")
    assert "sốt xuất huyết" in record["title"].lower()
    assert (record["url"] or "").startswith("https://moh.gov.vn/")


def test_source_hub_sync_vn_dav_html_crawl_parses_title_and_date(monkeypatch) -> None:
    token = _login("alice@research.clara")

    html_doc = """
    <html>
      <body>
        <a
          href="/thong-bao/thu-hoi-thuoc-ngay-01-04-2026.html"
          title="Thông báo thu hồi thuốc 01/04/2026"
        >
          Xem chi tiết
        </a>
        <a href="/thong-bao/lich-hop-noi-bo.html">Lịch họp nội bộ</a>
      </body>
    </html>
    """

    def _fake_http_get_text(url: str, *, params: dict[str, object] | None = None) -> str:
        assert "dav.gov.vn" in url
        assert params is None
        return html_doc

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._http_get_text",
        _fake_http_get_text,
    )

    response = client.post(
        "/api/v1/research/source-hub/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "vn_dav", "query": "thu hoi", "limit": 20},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "vn_dav"
    assert payload["fetched"] == 1
    record = payload["records"][0]
    assert record["id"].startswith("vn_dav:")
    assert "thu hồi thuốc" in record["title"].lower()
    assert record["published_at"] == "2026-04-01"
    assert (record["url"] or "").startswith("https://dav.gov.vn/")


def test_source_hub_sync_limit_clamp_min_3_and_max_500(monkeypatch) -> None:
    token = _login("alice@research.clara")
    observed_limits: list[int] = []

    def _fake_fetch_source_hub_records(source: str, query: str, limit: int):
        _ = source, query
        observed_limits.append(limit)
        return [], []

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.research._fetch_source_hub_records",
        _fake_fetch_source_hub_records,
    )

    low_limit_response = client.post(
        "/api/v1/research/source-hub/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "vn_kcb", "query": "huong dan", "limit": 1},
    )
    assert low_limit_response.status_code == 200

    high_limit_response = client.post(
        "/api/v1/research/source-hub/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"source": "vn_kcb", "query": "huong dan", "limit": 500},
    )
    assert high_limit_response.status_code == 200
    assert observed_limits == [3, 500]
