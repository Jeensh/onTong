"use client";

interface DomainSelectProps {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  label: string;
}

export function DomainSelect({
  value,
  options,
  onChange,
  label,
}: DomainSelectProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {label}
      </span>
      <select
        className="h-7 rounded-md border border-input bg-background px-2 text-xs outline-none focus:border-ring focus:ring-1 focus:ring-ring/50"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">--</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}
