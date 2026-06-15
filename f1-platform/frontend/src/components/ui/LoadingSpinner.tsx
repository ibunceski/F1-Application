export function LoadingSpinner() {
  return (
    <div className="flex min-h-40 items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-f1-border border-t-f1-red" />
    </div>
  );
}
