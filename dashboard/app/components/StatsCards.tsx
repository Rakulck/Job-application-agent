"use client";

interface Stats {
  total: number;
  applied: number;
  pending: number;
  skipped: number;
  failed: number;
}

export default function StatsCards({ stats }: { stats: Stats }) {
  const cards = [
    { label: "Total Scraped", value: stats.total, color: "bg-blue-50 border-blue-200 text-blue-700" },
    { label: "Applied", value: stats.applied, color: "bg-green-50 border-green-200 text-green-700" },
    { label: "Pending", value: stats.pending, color: "bg-yellow-50 border-yellow-200 text-yellow-700" },
    { label: "Skipped", value: stats.skipped, color: "bg-gray-50 border-gray-200 text-gray-600" },
    { label: "Failed", value: stats.failed, color: "bg-red-50 border-red-200 text-red-700" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
      {cards.map((c) => (
        <div key={c.label} className={`border rounded-xl p-4 ${c.color}`}>
          <p className="text-sm font-medium opacity-75">{c.label}</p>
          <p className="text-3xl font-bold mt-1">{c.value}</p>
        </div>
      ))}
    </div>
  );
}
