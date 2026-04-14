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
  const isCustomValue = value && !options.includes(value);

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {label}
      </span>
      <div className="relative">
        <select
          className={`h-7 rounded-md border bg-background px-2 text-xs outline-none focus:border-ring focus:ring-1 focus:ring-ring/50 ${
            isCustomValue ? "border-yellow-400" : "border-input"
          }`}
          value={options.includes(value) ? value : ""}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">--</option>
          {isCustomValue && (
            <option value="" disabled>
              {value} (템플릿 외)
            </option>
          )}
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        {isCustomValue && (
          <span className="absolute -bottom-4 left-0 text-[10px] text-yellow-600 dark:text-yellow-400 whitespace-nowrap">
            새 {label.toLowerCase()}
          </span>
        )}
      </div>
    </div>
  );
}
