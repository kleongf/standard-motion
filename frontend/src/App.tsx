import { AuditPage } from "./features/audit/AuditPage";
import { usePage } from "./features/core/pages";
import { Sidebar } from "./features/core/Sidebar";
import { PreparePage } from "./features/dataset/PreparePage";
import { EpisodesPage } from "./features/episodes/EpisodesPage";
import { EvaluationPage } from "./features/evaluation/EvaluationPage";
import { ReferenceLabelsPage } from "./features/referenceLabels/ReferenceLabelsPage";
import { ReviewPage } from "./features/review/ReviewPage";
import { DescribePage } from "./features/rubric/DescribePage";
import { SelectionPage } from "./features/selection/SelectionPage";

export function App() {
  const [page, setPage] = usePage();
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar page={page} onPage={setPage} />
      <main className="min-w-0 flex-1 overflow-x-clip">
        {page === "prepare" && <PreparePage />}
        {page === "select" && <SelectionPage />}
        {page === "describe" && <DescribePage />}
        {page === "episodes" && <EpisodesPage />}
        {page === "review" && <ReviewPage />}
        {page === "audit" && <AuditPage />}
        {page === "reference" && <ReferenceLabelsPage />}
        {page === "evaluation" && <EvaluationPage />}
      </main>
    </div>
  );
}
