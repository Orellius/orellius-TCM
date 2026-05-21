interface MediaPreviewProps {
  mediaUrls: string[];
  stampEnabled: boolean;
}

export function MediaPreview({ mediaUrls, stampEnabled }: MediaPreviewProps) {
  if (mediaUrls.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          Media ({mediaUrls.length})
        </h3>
        {stampEnabled && (
          <span className="rounded-full bg-[var(--accent-blue)] px-2 py-0.5 text-xs text-white">
            Stamped
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {mediaUrls.map((url, i) => (
          <div
            key={url}
            className="aspect-square rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] flex items-center justify-center"
          >
            <span className="text-xs text-[var(--text-secondary)]">
              {url.endsWith(".mp4") || url.endsWith(".mov") ? "Video" : "Image"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
