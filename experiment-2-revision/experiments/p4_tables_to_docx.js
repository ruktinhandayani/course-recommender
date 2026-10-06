// P4d - render results/tables/tables.json into results/tables/Tables_main_and_supplement.docx (A4 landscape, three-rule tables, Arial).
const fs = require("fs"), path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, BorderStyle, AlignmentType, PageOrientation, VerticalAlign, ShadingType } = require("docx");
const ROOT = path.resolve(__dirname, ".."), T = JSON.parse(fs.readFileSync(path.join(ROOT, "results/tables/tables.json"), "utf8"));
const CONTENT = 16838 - 2 * 1000, FONT = "Arial";
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, thick = { style: BorderStyle.SINGLE, size: 10, color: "000000" }, thin = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const label = (id) => (id.startsWith("T") ? "Table " + id.slice(1) : "Table " + id);

function widths(t, ncol) {
  const hs = Array.isArray(t.header[0]) ? t.header : [t.header];
  const len = Array(ncol).fill(4);
  for (const r of [...hs, ...t.rows]) r.forEach((c, j) => { len[j] = Math.max(len[j], Math.min(String(c).length, (j === 1 && t.id === "S7") || (j === 3 && t.id === "S6") ? 60 : 46)); });
  const w = len.map((l, j) => (j === 0 ? l * 1.15 : l) + 4), s = w.reduce((a, b) => a + b, 0);
  const out = w.map((x) => Math.floor((x / s) * CONTENT)); out[0] += CONTENT - out.reduce((a, b) => a + b, 0); return out;
}
const run = (text, o = {}) => new TextRun({ text: String(text), font: FONT, size: o.size || 16, bold: !!o.bold, italics: !!o.italics });
function cell(text, w, o = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA }, columnSpan: o.span, rowSpan: o.rowSpan, verticalAlign: VerticalAlign.CENTER,
    margins: { top: 35, bottom: 35, left: 70, right: 70 },
    borders: { top: o.top || none, bottom: o.bottom || none, left: none, right: none },
    children: [new Paragraph({ alignment: o.left ? AlignmentType.LEFT : AlignmentType.CENTER, children: [run(text, { bold: o.bold })] })],
  });
}
function build(t) {
  const hs = Array.isArray(t.header[0]) ? t.header : [t.header], ncol = hs[hs.length - 1].length, w = widths(t, ncol), rows = [];
  const groupAt = {}; (t.groups || []).forEach(([a, b]) => { groupAt[a] = b; });
  const inGroup = (j) => (t.groups || []).some(([a, b]) => j > a && j <= b);
  const nh = hs.length, sp = (a, b) => w.slice(a, b + 1).reduce((x, y) => x + y, 0);
  hs.forEach((h, ri) => {
    const cells = [];
    for (let j = 0; j < ncol; j++) {
      const top = ri === 0 ? thick : undefined, bottom = ri === nh - 1 ? thin : undefined;
      if (nh === 2 && ri === 0 && groupAt[j] !== undefined) { cells.push(cell(h[j], sp(j, groupAt[j]), { span: groupAt[j] - j + 1, bold: true, top, bottom: thin })); continue; }
      if (nh === 2 && ri === 0 && inGroup(j)) continue;
      if (nh === 2 && ri === 0 && hs[1][j] === "" ) { cells.push(cell(h[j], w[j], { rowSpan: 2, bold: true, left: j === 0, top, bottom: thin })); continue; }
      if (nh === 2 && ri === 1 && hs[1][j] === "" ) continue;
      cells.push(cell(h[j], w[j], { bold: true, left: j === 0, top, bottom }));
    }
    rows.push(new TableRow({ tableHeader: true, children: cells }));
  });
  const bold = new Set(t.bold.map(([r, c]) => r + "," + c));
  t.rows.forEach((r, i) => {
    const last = i === t.rows.length - 1, sect = r.slice(1).every((c) => c === "") && t.id === "T2";
    rows.push(new TableRow({ children: r.map((c, j) => cell(c, w[j], { left: j === 0 || (t.id === "S7" && j === 1) || (t.id === "S6" && (j === 1 || j === 3)), bold: bold.has(i + "," + j) || sect, bottom: last ? thick : undefined })) }));
  });
  return [
    new Paragraph({ spacing: { before: 0, after: 100 }, keepNext: true, children: [run(label(t.id) + ". ", { bold: true, size: 19 }), run(t.title, { size: 19 })] }),
    new Table({ width: { size: CONTENT, type: WidthType.DXA }, columnWidths: w, rows }),
    new Paragraph({ spacing: { before: 90, after: 0 }, children: [run(t.notes, { size: 15 })] }),
  ];
}
const children = [];
t_order = T; t_order.forEach((t, i) => { children.push(...build(t)); if (i < T.length - 1) children.push(new Paragraph({ pageBreakBefore: true, children: [] })); });
const doc = new Document({
  creator: "JCMM revision experiments", title: "Tables", styles: { default: { document: { run: { font: FONT, size: 16 } } } },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838, orientation: PageOrientation.LANDSCAPE }, margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } }, children }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(path.join(ROOT, "results/tables/Tables_main_and_supplement.docx"), b); console.log("wrote docx,", T.length, "tables"); });
