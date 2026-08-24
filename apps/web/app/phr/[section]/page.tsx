"use client";

import React, { use } from "react";
import { useParams } from "next/navigation";
import RecordSectionEditor from "@/components/phr/record-section-editor";

interface PhrSectionPageProps {
  params?: Promise<{ section: string }>;
}

export default function PhrSectionPage({ params }: PhrSectionPageProps) {
  const routeParams = useParams<{ section?: string }>();
  let resolvedSection = routeParams?.section;

  if (!resolvedSection && params) {
    const unwrapped = use(params);
    resolvedSection = unwrapped?.section;
  }

  return <RecordSectionEditor section={resolvedSection ?? ""} />;
}
