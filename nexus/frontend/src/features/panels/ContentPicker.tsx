export interface ContentPickerOption {
  id: string;
  label: string;
  location?: string;
}

interface ContentPickerProps {
  label: string;
  value: string;
  options: readonly ContentPickerOption[];
  onChange: (contentId: string) => void;
  className?: string;
}

export function ContentPicker({ label, value, options, onChange, className }: ContentPickerProps) {
  return (
    <select className={className} aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
      {value === '' && <option value="" disabled>Select content</option>}
      {options.map((option) => (
        <option key={option.id} value={option.id}>{option.location && option.id !== value ? `${option.label} · ${option.location}` : option.label}</option>
      ))}
    </select>
  );
}
