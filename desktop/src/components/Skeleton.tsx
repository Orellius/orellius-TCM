/** Reusable skeleton loading primitives for shimmer effects. */

export function SkeletonLine({ width = "100%", className = "" }: { width?: string; className?: string }) {
  return (
    <div
      className={`h-3 animate-pulse rounded bg-[var(--bg-tertiary)] ${className}`}
      style={{ width }}
    />
  );
}

export function SkeletonBlock({ height = "4rem", className = "" }: { height?: string; className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-[var(--bg-tertiary)] ${className}`}
      style={{ height }}
    />
  );
}

export function SkeletonCircle({ size = "2rem", className = "" }: { size?: string; className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-full bg-[var(--bg-tertiary)] ${className}`}
      style={{ width: size, height: size }}
    />
  );
}

/** Skeleton for a message card in the feed */
export function MessageCardSkeleton() {
  return (
    <div className="px-3 py-2.5 border-s-2 border-s-transparent">
      <div className="flex items-center justify-between gap-1 mb-1">
        <div className="flex items-center gap-1.5">
          <SkeletonCircle size="0.5rem" />
          <SkeletonLine width="6rem" />
        </div>
        <SkeletonLine width="3rem" />
      </div>
      <SkeletonLine width="80%" className="mt-1.5" />
      <div className="flex items-center justify-between mt-1.5">
        <SkeletonLine width="4rem" />
        <SkeletonLine width="3rem" />
      </div>
    </div>
  );
}

/** Skeleton for the dossier view while a message is being processed */
export function DossierSkeleton() {
  return (
    <div className="flex h-full flex-col">
      {/* Header skeleton */}
      <div className="flex items-center justify-between border-b border-[var(--border-color)] px-6 py-3">
        <div className="flex items-center gap-3">
          <SkeletonLine width="5rem" className="h-5 rounded-full" />
          <SkeletonLine width="8rem" />
        </div>
        <SkeletonLine width="4rem" />
      </div>

      <div className="flex-1 space-y-4 p-6">
        {/* Source section skeleton */}
        <div>
          <SkeletonLine width="3rem" className="mb-2 h-2.5" />
          <SkeletonBlock height="5rem" />
        </div>

        {/* Tags skeleton */}
        <div>
          <SkeletonLine width="3rem" className="mb-2 h-2.5" />
          <div className="flex gap-1.5">
            <SkeletonLine width="4rem" className="h-5 rounded-full" />
            <SkeletonLine width="5rem" className="h-5 rounded-full" />
            <SkeletonLine width="3rem" className="h-5 rounded-full" />
            <SkeletonLine width="4.5rem" className="h-5 rounded-full" />
          </div>
        </div>

        {/* Facts skeleton */}
        <div>
          <SkeletonLine width="5rem" className="mb-2 h-2.5" />
          <SkeletonBlock height="4rem" />
        </div>

        {/* Title skeleton */}
        <div>
          <SkeletonLine width="3rem" className="mb-2 h-2.5" />
          <SkeletonLine width="100%" className="h-8 rounded-md" />
        </div>

        {/* Output skeleton */}
        <div>
          <SkeletonLine width="5rem" className="mb-2 h-2.5" />
          <SkeletonBlock height="8rem" />
        </div>
      </div>

      {/* Action bar skeleton */}
      <div className="flex items-center justify-between border-t border-[var(--border-color)] px-6 py-3">
        <div className="flex gap-2">
          <SkeletonLine width="7rem" className="h-8 rounded-md" />
          <SkeletonLine width="5rem" className="h-8 rounded-md" />
        </div>
        <SkeletonLine width="10rem" />
      </div>
    </div>
  );
}
