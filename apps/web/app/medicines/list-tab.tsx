"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field } from "@/components/ui/field";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import {
  checkDrugBankDdi,
  correctMedicationCourse,
  createMedicationCourse,
  endMedicationCourse,
  getMedicationCourses,
  type DrugBankDdiResult,
  type MedicationCourse,
} from "@/lib/medication-courses";

export default function MedicinesListTab() {
  const [courses, setCourses] = useState<MedicationCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DrugBankDdiResult | null>(null);
  const [name, setName] = useState("");
  const [dose, setDose] = useState("");
  const [schedule, setSchedule] = useState("");
  const [drugbankId, setDrugbankId] = useState("");
  const [route, setRoute] = useState("");
  const [form, setForm] = useState("");
  const [editing, setEditing] = useState<MedicationCourse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setCourses(await getMedicationCourses());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Kiểm tra kết nối rồi thử lại.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const add = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError("");
    try {
      if (editing) {
        await correctMedicationCourse(editing.id, editing.version, {
          medication_name: name.trim(),
          dose_text: dose.trim(),
          schedule_text: schedule.trim(),
          route_text: route.trim(),
          form_text: form.trim(),
          reason: "Người dùng chỉnh sửa theo nguồn đang có",
        });
      } else {
        await createMedicationCourse({
          medication_name: name.trim(),
          dose_text: dose.trim(),
          schedule_text: schedule.trim(),
          route_text: route.trim(),
          form_text: form.trim(),
          drugbank_id: drugbankId.trim() || undefined,
        });
      }
      setName("");
      setDose("");
      setSchedule("");
      setDrugbankId("");
      setRoute("");
      setForm("");
      setEditing(null);
      setResult(null);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lưu thuốc.");
    } finally {
      setSaving(false);
    }
  };

  const check = async () => {
    setChecking(true);
    setError("");
    setResult(null);
    try {
      setResult(
        await checkDrugBankDdi(
          courses
            .filter((course) => course.status === "active")
            .map((course) => course.id),
        ),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể hoàn tất kiểm tra tương tác.");
    } finally {
      setChecking(false);
    }
  };

  const edit = (course: MedicationCourse) => {
    setEditing(course);
    setName(course.medication_name);
    setDose(course.dose_text);
    setSchedule(course.schedule_text);
    setRoute(course.route_text);
    setForm(course.form_text);
    setDrugbankId(course.drugbank_id ?? "");
  };

  const end = async (course: MedicationCourse) => {
    if (
      !window.confirm(
        "Xác nhận ghi nhận thuốc này đã kết thúc? Đây chỉ là cập nhật hồ sơ, không phải lời khuyên ngừng thuốc.",
      )
    ) {
      return;
    }
    setSaving(true);
    setError("");
    try {
      await endMedicationCourse(
        course.id,
        course.version,
        "Người dùng cập nhật trạng thái hồ sơ",
      );
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể cập nhật thuốc.");
    } finally {
      setSaving(false);
    }
  };

  const activeCourses = courses.filter((course) => course.status === "active");

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-5">
        {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

        {loading ? (
          <LoadingCards count={2} />
        ) : (
          <>
            <SurfaceCard className="overflow-hidden">
              <div className="flex flex-col gap-3 border-b border-[color:var(--shell-border)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="font-semibold text-[var(--text-primary)]">Thuốc đang theo dõi</h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Chỉ dữ liệu bạn xác nhận mới có mặt ở đây.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button as="link" href="/medicines/add" size="sm" icon="add">
                    Thêm thuốc theo từng bước
                  </Button>
                  <Button
                    size="sm"
                    disabled={activeCourses.length < 2}
                    loading={checking}
                    loadingLabel="Đang đối chiếu DrugBank…"
                    onClick={() => void check()}
                    icon="labs"
                  >
                    Kiểm tra tương tác DrugBank
                  </Button>
                </div>
              </div>
              {courses.length ? (
                <ul className="divide-y divide-[color:var(--shell-border)]">
                  {courses.map((course) => (
                    <li key={course.id} className="flex items-start gap-3 px-5 py-4">
                      <span
                        className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                        aria-hidden="true"
                      >
                        <span className="material-symbols-outlined">medication</span>
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-[var(--text-primary)]">
                          {course.medication_name}
                        </p>
                        <p className="mt-0.5 text-sm text-[var(--text-secondary)]">
                          {[
                            course.dose_text,
                            course.schedule_text,
                            course.route_text,
                            course.form_text,
                          ].filter(Boolean).join(" · ") ||
                            "Chưa có liều/lịch dùng"}
                        </p>
                        {course.drugbank_id ? (
                          <p className="mt-1 text-xs text-[var(--text-muted)]">
                            DrugBank ID: {course.drugbank_id}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2">
                        <Badge
                          tone={course.status === "active" ? "ok" : "neutral"}
                          icon={course.status === "active" ? "check_circle" : "history"}
                        >
                          {course.status === "active" ? "Đang theo dõi" : "Đã kết thúc"}
                        </Badge>
                        <Badge
                          tone={
                            course.reconciliation_status === "matched" ? "brand" : "warn"
                          }
                        >
                          {course.reconciliation_status === "matched"
                            ? "Đã đối chiếu"
                            : "Chưa đối chiếu chuẩn"}
                        </Badge>
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            icon="edit"
                            onClick={() => edit(course)}
                          >
                            Sửa
                          </Button>
                          {course.status === "active" ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              icon="stop_circle"
                              onClick={() => void end(course)}
                            >
                              Kết thúc
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-5">
                  <EmptyState
                    icon="medication"
                    title="Chưa có thuốc nào"
                    description="Thêm thuốc bạn đang dùng để theo dõi. Đừng dùng danh sách này thay cho đơn hoặc hướng dẫn của bác sĩ."
                  />
                </div>
              )}
            </SurfaceCard>

            {result ? (
              <SurfaceCard className="p-5">
                <div className="flex items-start gap-3">
                  <span
                    className="material-symbols-outlined text-[var(--status-ok-text)]"
                    aria-hidden="true"
                  >
                    verified
                  </span>
                  <div>
                    <p className="font-semibold text-[var(--text-primary)]">
                      Kết quả đã đối chiếu DrugBank
                    </p>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      Nguồn phiên bản: {result.source_version}
                    </p>
                  </div>
                </div>
                {result.ddi_alerts.length ? (
                  <ul className="mt-4 space-y-2">
                    {result.ddi_alerts.map((alert, index) => (
                      <li
                        key={index}
                        className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-sm text-[var(--status-warn-text)]"
                      >
                        <p className="font-semibold">{alert.severity ?? "Cảnh báo"}</p>
                        <p className="mt-1">
                          {alert.message ||
                            "Có tương tác cần được dược sĩ hoặc bác sĩ đánh giá."}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3 text-sm text-[var(--status-ok-text)]">
                    DrugBank không ghi nhận cảnh báo DDI cho các thuốc đã chọn trong lần đối chiếu
                    này. Điều này không thay thế tư vấn cá nhân từ dược sĩ hoặc bác sĩ.
                  </p>
                )}
                {result.recommendation ? (
                  <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                    {result.recommendation}
                  </p>
                ) : null}
              </SurfaceCard>
            ) : null}
          </>
        )}
      </div>

      <aside className="space-y-5">
        <SurfaceCard className="p-5">
          <h2 className="font-semibold text-[var(--text-primary)]">
            {editing ? "Sửa bản ghi thuốc" : "Thêm thuốc đã xác nhận"}
          </h2>
          <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
            Nhập theo nhãn hoặc đơn của bạn; CLARA không suy đoán thuốc.
          </p>
          <form className="mt-4 space-y-3.5" onSubmit={(event) => void add(event)}>
            <Field
              label="Tên thuốc"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Field
              label="Liều dùng"
              optional
              value={dose}
              onChange={(event) => setDose(event.target.value)}
              placeholder="Ví dụ: 500 mg"
            />
            <Field
              label="Lịch dùng"
              optional
              value={schedule}
              onChange={(event) => setSchedule(event.target.value)}
              placeholder="Ví dụ: buổi tối"
            />
            <Field
              label="Đường dùng"
              optional
              value={route}
              onChange={(event) => setRoute(event.target.value)}
              placeholder="Ví dụ: uống"
            />
            <Field
              label="Dạng bào chế"
              optional
              value={form}
              onChange={(event) => setForm(event.target.value)}
              placeholder="Ví dụ: viên nén"
            />
            <Field
              label="DrugBank ID"
              optional
              value={drugbankId}
              onChange={(event) => setDrugbankId(event.target.value)}
              placeholder="DB…"
            />
            <Button
              type="submit"
              variant="secondary"
              block
              loading={saving}
              loadingLabel="Đang lưu…"
              icon="save"
            >
              {editing ? "Lưu phiên bản mới" : "Lưu thuốc đã xác nhận"}
            </Button>
            {editing ? (
              <Button
                type="button"
                variant="ghost"
                block
                onClick={() => {
                  setEditing(null);
                  setName("");
                  setDose("");
                  setSchedule("");
                  setRoute("");
                  setForm("");
                  setDrugbankId("");
                }}
              >
                Hủy chỉnh sửa
              </Button>
            ) : null}
          </form>
        </SurfaceCard>

        <SurfaceCard className="p-5">
          <h2 className="font-semibold text-[var(--text-primary)]">Tủ thuốc</h2>
          <p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">
            Quét nhãn, theo dõi hạn dùng và quản lý các mục trong tủ thuốc tại tab riêng.
          </p>
          <Link
            href="/medicines?tab=cabinet"
            className="focus-ring mt-4 inline-flex items-center gap-1 rounded-lg text-sm font-semibold text-[var(--text-brand)] hover:underline"
          >
            Mở tủ thuốc
            <span className="material-symbols-outlined text-base" aria-hidden="true">
              arrow_forward
            </span>
          </Link>
        </SurfaceCard>
      </aside>
    </div>
  );
}
