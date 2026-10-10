/** Saves text as a file in the browser. CSV gets a BOM so Excel reads Thai text as UTF-8. */
export function downloadText(fileName: string, text: string, type: 'application/json' | 'text/csv'): void {
  const body = type === 'text/csv' ? `﻿${text}` : text;
  const url = URL.createObjectURL(new Blob([body], { type: `${type};charset=utf-8` }));
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
