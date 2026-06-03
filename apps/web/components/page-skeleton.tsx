type Props = {
  title: string;
  description: string;
};

export default function PageSkeleton({ title, description }: Props) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-bold tracking-[-0.02em] text-slate-900">{title}</h1>
      <p className="mt-2 text-slate-600">{description}</p>
      <div className="mt-6 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">Module A (skeleton)</div>
        <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">Module B (skeleton)</div>
        <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">Module C (skeleton)</div>
        <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">Module D (skeleton)</div>
      </div>
    </section>
  );
}
