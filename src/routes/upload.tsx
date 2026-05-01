import { createFileRoute } from "@tanstack/react-router";
import { UploadPage } from "@/components/UploadPage";

export const Route = createFileRoute("/upload")({
  component: UploadPage,
});