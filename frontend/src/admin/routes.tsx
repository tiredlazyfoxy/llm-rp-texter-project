import { Routes, Route, useParams } from "react-router-dom";
import { UsersPage } from "./pages/UsersPage";
import { WorldsListPage } from "./pages/WorldsListPage";
import { WorldViewPage } from "./pages/WorldViewPage";
import { WorldEditPage } from "./pages/WorldEditPage";
import { WorldFieldEditPage } from "./pages/WorldFieldEditPage";
import { DocumentEditPage } from "./pages/DocumentEditPage";
import { PipelinesListPage } from "./pages/PipelinesListPage";
import { PipelineEditPage } from "./pages/PipelineEditPage";
import { PipelineStageEditPage } from "./pages/PipelineStageEditPage";
import { LlmServersPage } from "./pages/LlmServersPage";
import { DbManagementPage } from "./pages/DbManagementPage";

const WorldViewPageRoute = () => {
  const { worldId } = useParams<{ worldId: string }>();
  return <WorldViewPage key={worldId} worldId={worldId!} />;
};

const WorldEditPageRoute = () => {
  const { worldId } = useParams<{ worldId: string }>();
  return <WorldEditPage key={worldId} worldId={worldId!} />;
};

const WorldFieldEditPageRoute = () => {
  const { worldId, fieldName } = useParams<{ worldId: string; fieldName: string }>();
  const safeField = (fieldName === "description" || fieldName === "initial_message")
    ? fieldName
    : "description";
  return (
    <WorldFieldEditPage
      key={`${worldId}:${fieldName}`}
      worldId={worldId!}
      fieldName={safeField}
    />
  );
};

const DocumentEditPageRoute = () => {
  const { worldId, docId } = useParams<{ worldId: string; docId: string }>();
  return <DocumentEditPage key={`${worldId}:${docId}`} worldId={worldId!} docId={docId!} />;
};

const PipelineEditPageRoute = () => {
  const { pipelineId } = useParams<{ pipelineId: string }>();
  return <PipelineEditPage key={pipelineId} />;
};

const PipelineStageEditPageRoute = () => {
  const { pipelineId, stageIndex } = useParams<{ pipelineId: string; stageIndex: string }>();
  return <PipelineStageEditPage key={`${pipelineId}:${stageIndex}`} />;
};

export function AdminRoutes() {
  return (
    <Routes>
      <Route path="/" element={<UsersPage />} />
      <Route path="/worlds" element={<WorldsListPage />} />
      <Route path="/worlds/:worldId" element={<WorldViewPageRoute />} />
      <Route path="/worlds/:worldId/edit" element={<WorldEditPageRoute />} />
      <Route path="/worlds/:worldId/field/:fieldName" element={<WorldFieldEditPageRoute />} />
      <Route path="/worlds/:worldId/documents/:docId/edit" element={<DocumentEditPageRoute />} />
      <Route path="/pipelines" element={<PipelinesListPage />} />
      <Route path="/pipelines/new" element={<PipelineEditPage key="new" />} />
      <Route path="/pipelines/:pipelineId" element={<PipelineEditPageRoute />} />
      <Route path="/pipelines/:pipelineId/stage/:stageIndex" element={<PipelineStageEditPageRoute />} />
      <Route path="/llm-servers" element={<LlmServersPage />} />
      <Route path="/database" element={<DbManagementPage />} />
    </Routes>
  );
}
