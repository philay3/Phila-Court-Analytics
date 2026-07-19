/**
 * Sample label (task 13.1; reconciled task 35.3). Renders a pre-formatted
 * sample label produced by the 11.4 formatters — the caller picks the
 * unit-naming formatter for its block (records / sentence components /
 * sentenced convictions per pin 11), so this component stays generic and no
 * label string is ever re-typed inline.
 */
interface SampleSizeLabelProps {
  /** The fully formatted label, e.g. from `formatRecordsLabel`. */
  label: string;
}

export function SampleSizeLabel({ label }: SampleSizeLabelProps) {
  return <p className="text-sm text-faint">{label}</p>;
}
