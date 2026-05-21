interface SettingRowProps {
  label: string;
  description?: string;
  children: React.ReactNode;
}

export function SettingRow({ label, description, children }: SettingRowProps) {
  return (
    <div className="flex items-center gap-3">
      {children}
      <div>
        <span className="text-sm text-[var(--text-primary)]">{label}</span>
        {description && (
          <p className="text-xs text-[var(--text-secondary)]">{description}</p>
        )}
      </div>
    </div>
  );
}
