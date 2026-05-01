import { Alert, Container } from "@mantine/core";

export function PipelineStageEditPage() {
  return (
    <Container size="lg" py="md">
      <Alert color="yellow" title="Stage editor moved">
        The pipeline-stage prompt editor is being relocated to
        /admin/pipelines/:pipelineId/stage/:stageIndex as part of step 002.
      </Alert>
    </Container>
  );
}
