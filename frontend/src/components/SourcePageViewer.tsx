"use client";

import { useEffect, useRef } from "react";
import { ExternalLink, Loader2 } from "lucide-react";
import { usePage } from "@/hooks/useAnalysis";
import { documentFileUrl } from "@/lib/api";

const REGEX_SPECIALS = /[.*+?^${}()|[\]\\]/g;

/** Split `text` around the first whitespace-insensitive occurrence of `excerpt` so it can be highlighted. */
function splitAtExcerpt(text: string, excerpt: string): [string, string, string] | null {
  const words = excerpt.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return null;
  try {
    const pattern = words.map((w) => w.replace(REGEX_SPECIALS, "\\$&")).join("\\s+");
    const m = new RegExp(pattern, "i").exec(text);
    if (!m) return null;
    return [text.slice(0, m.index), m[0], text.slice(m.index + m[0].length)];
  } catch {
    return null;
  }
}

export function SourcePageViewer({
  documentId,
  page,
  excerpt,
}: {
  documentId: string;
  page: number;
  excerpt: string;
}) {
  const { data, isLoading, error } = usePage(documentId, page);
  const parts = data ? splitAtExcerpt(data.text, excerpt) : null;
  const markRef = useRef<HTMLElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  // Scroll the highlighted excerpt into view inside the page box (without moving the whole dialog).
  useEffect(() => {
    const mark = markRef.current;
    const box = boxRef.current;
    if (mark && box) box.scrollTop = Math.max(0, mark.offsetTop - box.clientHeight / 3);
  }, [parts?.[1]]);

  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-100 px-3 py-1.5 text-xs text-slate-500">
        <span>
          Page {page} text
          {data?.extraction_method === "ocr" && (
            <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-amber-700">OCR</span>
          )}
        </span>
        <a
          href={`${documentFileUrl(documentId)}#page=${page}`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline"
        >
          Open PDF <ExternalLink className="h-3 w-3" />
        </a>
      </div>
      <div ref={boxRef} className="relative max-h-56 overflow-y-auto whitespace-pre-wrap px-3 py-2 text-xs leading-relaxed text-slate-600">
        {isLoading && (
          <span className="inline-flex items-center gap-1.5 text-slate-400">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading page…
          </span>
        )}
        {error && <span className="text-red-600">Could not load this page.</span>}
        {data &&
          (parts ? (
            <>
              {parts[0]}
              <mark ref={markRef} className="rounded bg-yellow-200 px-0.5 text-slate-900">{parts[1]}</mark>
              {parts[2]}
            </>
          ) : (
            data.text
          ))}
      </div>
    </div>
  );
}
