import fs from "node:fs";
import path from "node:path";

const [reportPath, outputPath] = process.argv.slice(2);
if (!reportPath || !outputPath) {
  throw new Error("Usage: node extract_embedded_panel.mjs <index.html> <output.csv>");
}

const lines = fs.readFileSync(reportPath, "utf8").split(/\r?\n/);
const prefix = "const REF=";
const line = lines.find((candidate) => candidate.startsWith(prefix));
if (!line) throw new Error("The report does not contain an embedded REF panel");
const reference = Function(`"use strict"; return (${line.slice(prefix.length, -1)});`)();

function csvCell(value) {
  if (value == null) return "";
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

const rows = [reference.wcols, ...reference.wrows];
const csv = `${rows.map((row) => row.map(csvCell).join(",")).join("\n")}\n`;
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, csv, "utf8");
console.log(`Wrote ${reference.wrows.length} rows and ${reference.wcols.length} columns to ${outputPath}`);
