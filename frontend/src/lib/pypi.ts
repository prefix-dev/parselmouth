/**
 * PEP 503 normalization: lowercase and collapse runs of `[-_.]` to a single `-`.
 * https://peps.python.org/pep-0503/#normalized-names
 */
export function normalizePypi(name: string): string {
  return name.toLowerCase().replace(/[-_.]+/g, "-");
}
