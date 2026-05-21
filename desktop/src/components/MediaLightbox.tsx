import { useEffect, useCallback } from "react";
import { createPortal } from "react-dom";

interface MediaLightboxProps {
  urls: string[];
  currentIndex: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
}

export function MediaLightbox({ urls, currentIndex, onClose, onNavigate }: MediaLightboxProps) {
  const url = urls[currentIndex];
  const isVideo = /\.(mp4|mov|webm|avi)$/i.test(url);
  const hasMultiple = urls.length > 1;

  const handlePrev = useCallback(() => {
    onNavigate((currentIndex - 1 + urls.length) % urls.length);
  }, [currentIndex, urls.length, onNavigate]);

  const handleNext = useCallback(() => {
    onNavigate((currentIndex + 1) % urls.length);
  }, [currentIndex, urls.length, onNavigate]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") handlePrev();
      if (e.key === "ArrowRight" || e.key === "ArrowDown") handleNext();
    }

    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose, handlePrev, handleNext]);

  const mediaSrc = `http://127.0.0.1:8000/media/${url}`;

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/85"
      onClick={onClose}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 end-4 rounded-full bg-white/10 p-2 text-white transition-colors hover:bg-white/20"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
          <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
        </svg>
      </button>

      {/* Counter */}
      {hasMultiple && (
        <span className="absolute top-4 start-4 rounded-full bg-white/10 px-3 py-1 text-sm text-white">
          {currentIndex + 1} / {urls.length}
        </span>
      )}

      {/* Previous */}
      {hasMultiple && (
        <button
          onClick={(e) => { e.stopPropagation(); handlePrev(); }}
          className="absolute start-4 top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white transition-colors hover:bg-white/20"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-6 w-6">
            <path fillRule="evenodd" d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.06 10l3.72 3.72a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
          </svg>
        </button>
      )}

      {/* Media content */}
      <div onClick={(e) => e.stopPropagation()} className="max-h-[85vh] max-w-[85vw]">
        {isVideo ? (
          <video
            src={mediaSrc}
            controls
            autoPlay
            className="max-h-[85vh] max-w-[85vw] rounded-lg"
          />
        ) : (
          <img
            src={mediaSrc}
            alt={`Media ${currentIndex + 1}`}
            className="max-h-[85vh] max-w-[85vw] rounded-lg object-contain"
          />
        )}
      </div>

      {/* Next */}
      {hasMultiple && (
        <button
          onClick={(e) => { e.stopPropagation(); handleNext(); }}
          className="absolute end-4 top-1/2 -translate-y-1/2 rounded-full bg-white/10 p-2 text-white transition-colors hover:bg-white/20"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-6 w-6">
            <path fillRule="evenodd" d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L11.94 10 8.22 6.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
          </svg>
        </button>
      )}
    </div>,
    document.body,
  );
}
