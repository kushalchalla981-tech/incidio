import { AlertTriangle } from "lucide-react";

export default function ErrorState({
  title = "Something went wrong",
  message = "We couldn't load this data. Please try again.",
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      <div className="w-12 h-12 rounded-full bg-status-critical/10 text-status-critical grid place-items-center mb-4">
        <AlertTriangle size={20} />
      </div>
      <h3 className="text-[15px] font-semibold text-text-primary">{title}</h3>
      <p className="text-sm text-text-secondary mt-1 max-w-sm">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-medium text-text-primary bg-surface-base border border-border-strong rounded-md shadow-sm hover:bg-surface-sunken transition-colors duration-150"
        >
          Retry
        </button>
      )}
    </div>
  );
}