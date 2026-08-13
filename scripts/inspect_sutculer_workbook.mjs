import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = process.argv[2];
if (!inputPath) {
  throw new Error("Usage: inspect_sutculer_workbook.mjs <workbook.xlsx>");
}

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const sheetSummary = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 6000,
});
console.log(sheetSummary.ndjson);

const compact = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 18000,
  tableMaxRows: 18,
  tableMaxCols: 12,
  tableMaxCellChars: 120,
});
console.log(compact.ndjson);
