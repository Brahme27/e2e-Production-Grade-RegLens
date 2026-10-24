import { DocumentView } from "@/components/DocumentView";

export default async function DocumentPage({ params, searchParams }: PageProps<"/documents/[docId]">) {
  const { docId } = await params;
  const query = await searchParams;
  const pick = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value) ?? null;
  return <DocumentView docId={docId} initialVersion={pick(query.version)} highlightRef={pick(query.ref)} />;
}
