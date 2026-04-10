import ProfileForm from "@/app/components/ProfileForm";
import UnknownQuestionsPanel from "@/app/components/UnknownQuestionsPanel";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

export const dynamic = "force-dynamic";

async function getPendingCount() {
  try {
    const { count } = await supabase
      .from("unknown_questions")
      .select("id", { count: "exact", head: true })
      .is("answer", null);
    return count ?? 0;
  } catch {
    return 0;
  }
}

export default async function ProfilePage() {
  const pendingCount = await getPendingCount();

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
          <p className="text-gray-500 text-sm mt-1">Changes apply on the next pipeline run.</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-8">
          <ProfileForm />
        </div>

        {/* Unknown Questions section */}
        <div className="bg-white rounded-2xl shadow-sm border border-orange-100 p-6">
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-base font-semibold text-gray-800">Unanswered Questions</h2>
            {pendingCount > 0 && (
              <span className="text-xs bg-orange-100 text-orange-700 border border-orange-200 px-2 py-0.5 rounded-full font-medium">
                {pendingCount} pending
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mb-4">
            These questions appeared in Easy Apply forms but had no matching answer.
            Provide answers below — they'll be saved to your profile automatically.
          </p>
          <UnknownQuestionsPanel />
        </div>
      </div>
    </main>
  );
}
