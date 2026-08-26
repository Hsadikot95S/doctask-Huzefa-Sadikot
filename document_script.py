from pathlib import Path
import shutil, json, hashlib, zipfile, os, re, textwrap
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

base = Path("/Users/huzi/Desktop/superdocs-app/data/documents/public-golden-corpus")
if base.exists():
    shutil.rmtree(base)

for d in ["pdf","docx","html","markdown","txt"]:
    (base/"documents"/d).mkdir(parents=True)
(base/"annotations").mkdir()
(base/"scripts").mkdir()

# Unicode-capable PDF fonts.
for font in ["HeiseiMin-W3", "HYSMyeongJo-Medium"]:
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font))
    except Exception:
        pass

docs = [
    # id, filename, format, language, length, type, features, title, body
    ("DOC-001","document_001_en_short.pdf","pdf","en","short","brief",
     ["headings","paragraphs","list"],
     "Project Brief",
     ["Purpose: evaluate document ingestion and review workflows.",
      "The system should preserve structure while applying targeted edits.",
      "Acceptance criteria:",
      ["Upload succeeds.","Evidence remains traceable.","Exported output is reviewable."]]),
    ("DOC-002","document_002_en_table.pdf","pdf","en","medium","report",
     ["headings","paragraphs","table","list"],
     "Operations Report",
     ["This report summarizes a fictional quarterly operations review.",
      "The figures below are synthetic and created for the corpus.",
      "The main observation is that throughput improved while review latency remained stable.",
      ["Metric","Q1","Q2"],["Documents processed","120","165"],["Review latency (min)","14","13"],["Export success","98%","99%"]]),
    ("DOC-003","document_003_es_long.pdf","pdf","es","long","technical_report",
     ["headings","paragraphs","table","list"],
     "Informe Técnico",
     ["Este documento contiene datos sintéticos creados exclusivamente para el corpus de evaluación.",
      "El objetivo es probar documentos largos con secciones, listas y tablas.",
      "La primera sección describe el contexto y la segunda presenta observaciones.",
      ["Elemento","Estado","Prioridad"],["Ingesta","Completada","Alta"],["Revisión","En curso","Media"],["Exportación","Completada","Alta"]],
    ),
    ("DOC-004","document_004_ja_layout.pdf","pdf","ja","medium","memo",
     ["headings","paragraphs","list"],
     "運用メモ",
     ["この文書は評価用に作成したオリジナルのサンプルです。",
      "見出し、段落、箇条書きを含む文書の処理を確認します。",
      ["入力ファイルを確認する。","変更案をレビューする。","承認後に結果を出力する。"]]),
    ("DOC-005","document_005_en_table.docx","docx","en","medium","report",
     ["headings","paragraphs","table","list"],
     "Customer Support Summary",
     ["This synthetic document tests DOCX tables and structured sections.",
      "All names, numbers and examples are fictional.",
      ["Area","Tickets","Resolution"],["Billing","42","94%"],["Technical","58","91%"],["Account","31","97%"]]),
    ("DOC-006","document_006_hi.docx","docx","hi","medium","memo",
     ["headings","paragraphs","list"],
     "परियोजना समीक्षा",
     ["यह दस्तावेज़ मूल्यांकन के लिए स्वयं बनाया गया है।",
      "इसमें शीर्षक, अनुच्छेद और सूची शामिल हैं।",
      ["दस्तावेज़ अपलोड करें।","परिवर्तन की समीक्षा करें।","स्वीकृति के बाद निर्यात करें।"]]),
    ("DOC-007","document_007_fr_long.docx","docx","fr","long","technical_report",
     ["headings","paragraphs","table","list"],
     "Rapport de validation",
     ["Ce document est un exemple original créé pour tester la conservation de structure.",
      "Il contient plusieurs sections et un tableau de résultats.",
      "Les résultats sont fictifs et ne représentent aucune organisation réelle.",
      ["Contrôle","Résultat","Statut"],["Importation","100 %","Réussi"],["Analyse","96 %","Réussi"],["Export","99 %","Réussi"]]),
    ("DOC-008","document_008_de_short.docx","docx","de","short","letter",
     ["headings","paragraphs"],
     "Kurzes Anschreiben",
     ["Dies ist ein vollständig selbst erstelltes Beispieldokument.",
      "Es dient der Prüfung von DOCX-Text, Absätzen und Formatierung."]),
    ("DOC-009","document_009_en_html.html","html","en","short","article",
     ["headings","paragraphs","list","image"],
     "Document Editing Basics",
     ["This synthetic HTML page tests headings, lists and an embedded SVG diagram.",
      "The diagram is generated locally and contains no external assets.",
      ["Ingest the document.","Propose a change.","Review and export."]]),
    ("DOC-010","document_010_es_html.html","html","es","medium","guide",
     ["headings","paragraphs","table","image"],
     "Guía de revisión",
     ["Esta página es un documento original para pruebas de formato.",
      "Incluye una tabla y un diagrama SVG incrustado."],
    ),
    ("DOC-011","document_011_fr_html.html","html","fr","medium","policy",
     ["headings","paragraphs","list"],
     "Politique de traitement",
     ["Cette politique fictive décrit un flux de traitement documentaire.",
      "Elle est créée uniquement pour le corpus de test.",
      ["Les données sont conservées de manière traçable.","Les propositions nécessitent une revue humaine."]]),
    ("DOC-012","document_012_en.md","markdown","en","short","specification",
     ["headings","paragraphs","list","code"],
     "API Change Note",
     ["This synthetic Markdown document tests headings, lists and code blocks.",
      ["Endpoint added: `/documents/{id}/review`","Review decisions are persisted.","Exports remain deterministic."],
      "```python\nprint('synthetic corpus sample')\n```"]),
    ("DOC-013","document_013_de.md","markdown","de","medium","guide",
     ["headings","paragraphs","table","list"],
     "Leitfaden",
     ["Dieses Dokument wurde vollständig für den Testkorpus erstellt.",
      ["Schritt 1: Dokument laden","Schritt 2: Änderung prüfen","Schritt 3: Ergebnis exportieren"],
      "| Feld | Wert |\n|---|---|\n| Sprache | Deutsch |\n| Status | Beispiel |"]),
    ("DOC-014","document_014_en.txt","txt","en","short","plain_text",
     ["paragraphs"],
     "Plain Text Sample",
     ["This is an original plain-text document.",
      "It intentionally contains no markup so a baseline text-only case is available."]),
    ("DOC-015","document_015_hi.txt","txt","hi","medium","plain_text",
     ["paragraphs","list"],
     "सादा पाठ नमूना",
     ["यह एक मूल परीक्षण दस्तावेज़ है।",
      "यह केवल दस्तावेज़ प्रसंस्करण की जाँच के लिए बनाया गया है।",
      ["पाठ निकालें","परिणाम की समीक्षा करें","फ़ाइल निर्यात करें"]]),
]

def make_pdf(path, lang, title, blocks):
    font = "Helvetica"
    if lang == "ja":
        font = "HeiseiMin-W3"
    elif lang == "hi":
        font = "HYSMyeongJo-Medium"  # fallback if CID font unavailable; Hindi shaping is not guaranteed
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=styles["Title"], fontName=font, fontSize=18, leading=22)
    body_style = ParagraphStyle("B", parent=styles["BodyText"], fontName=font, fontSize=10.5, leading=15)
    story = [Paragraph(title, title_style), Spacer(1, 12)]
    for b in blocks:
        if isinstance(b, list):
            if b and isinstance(b[0], str) and len(b) == 3:
                # table-like rows are handled below
                continue
            story.append(ListFlowable([ListItem(Paragraph(str(x), body_style)) for x in b], # pyright: ignore[reportArgumentType]
                                      bulletType="bullet", leftIndent=18))
            story.append(Spacer(1, 8))
        elif isinstance(b, str):
            story.append(Paragraph(b, body_style))
            story.append(Spacer(1, 8))
    # Add table if there are 4+ list rows with 3 cells.
    rows = [b for b in blocks if isinstance(b, list) and len(b)==3 and all(isinstance(x,str) for x in b)]
    if rows:
        t = Table(rows, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),0.5,colors.grey),
            ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
            ("FONTNAME",(0,0),(-1,-1),font),
            ("FONTSIZE",(0,0),(-1,-1),8),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
        ]))
        story.append(Spacer(1,8)); story.append(t)
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=45,leftMargin=45,topMargin=45,bottomMargin=45).build(story)

def make_docx(path, title, blocks):
    d=Document()
    d.add_heading(title, level=1)
    for b in blocks:
        if isinstance(b, list):
            if len(b)==3 and all(isinstance(x,str) for x in b):
                continue
            for x in b:
                d.add_paragraph(str(x), style="List Bullet")
        elif isinstance(b,str):
            d.add_paragraph(b)
    rows=[b for b in blocks if isinstance(b,list) and len(b)==3 and all(isinstance(x,str) for x in b)]
    if rows:
        table=d.add_table(rows=len(rows), cols=3)
        table.style="Table Grid"
        for i,row in enumerate(rows):
            for j,val in enumerate(row):
                table.cell(i,j).text=val
    d.save(path)

def make_html(path, title, blocks, with_image=False):
    parts=[f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
    <style>body{{font-family:system-ui;max-width:800px;margin:40px auto;line-height:1.6}}
    table{{border-collapse:collapse}}td,th{{border:1px solid #999;padding:8px}}</style></head><body><h1>{title}</h1>"""]
    for b in blocks:
        if isinstance(b,list):
            if len(b)==3 and all(isinstance(x,str) for x in b):
                continue
            parts.append("<ul>"+"".join(f"<li>{x}</li>" for x in b)+"</ul>")
        elif isinstance(b,str):
            parts.append(f"<p>{b}</p>")
    rows=[b for b in blocks if isinstance(b,list) and len(b)==3 and all(isinstance(x,str) for x in b)]
    if rows:
        parts.append("<table>" + "".join("<tr>"+ "".join(f"<td>{x}</td>" for x in r)+"</tr>" for r in rows) + "</table>")
    if with_image:
        parts.append("""<svg width="520" height="100" role="img" aria-label="Synthetic workflow diagram">
        <rect x="10" y="30" width="130" height="40" fill="#eee" stroke="#333"/><text x="30" y="55">Input</text>
        <line x1="140" y1="50" x2="200" y2="50" stroke="#333"/>
        <rect x="200" y="30" width="130" height="40" fill="#eee" stroke="#333"/><text x="220" y="55">Review</text>
        <line x1="330" y1="50" x2="390" y2="50" stroke="#333"/>
        <rect x="390" y="30" width="120" height="40" fill="#eee" stroke="#333"/><text x="415" y="55">Export</text>
        </svg>""")
    parts.append("</body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")

def make_md(path, title, blocks):
    out=[f"# {title}",""]
    for b in blocks:
        if isinstance(b,list):
            if len(b)==3 and all(isinstance(x,str) for x in b):
                out.append("| Field | Value |"); out.append("|---|---|")
                for x in b: 
                    if "|" in x: 
                        k,v=[z.strip() for z in x.split("|",1)]
                        out.append(f"| {k} | {v} |")
                out.append("")
            else:
                out += [f"- {x}" for x in b]+[""]
        else:
            out += [b,""]
    path.write_text("\n".join(out), encoding="utf-8")

for did, fn, fmt, lang, length, dtype, features, title, blocks in docs:
    path = base/"documents"/fmt/fn
    if fmt=="pdf": make_pdf(path,lang,title,blocks)
    elif fmt=="docx": make_docx(path,title,blocks)
    elif fmt=="html": make_html(path,title,blocks,"image" in features)
    elif fmt=="markdown": make_md(path,title,blocks)
    else:
        path.write_text(title+"\n\n"+"\n\n".join(
            (("\n".join("- "+x for x in b)) if isinstance(b,list) else b) for b in blocks
        ), encoding="utf-8")

    data = path.read_bytes()
    rel = path.relative_to(base).as_posix()
    ann = {
        "id": did,
        "filename": rel,
        "format": fmt,
        "language": lang,
        "length_class": length,
        "document_type": dtype,
        "structural_features": features,
        "source": {
            "type": "self-authored",
            "description": "Original synthetic document created specifically for the SuperDocs evaluation corpus."
        },
        "license": {
            "name": "CC0 1.0 Universal",
            "url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "verified": True,
            "verification_method": "Self-authored corpus material; no third-party content or assets used."
        },
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data)
    }
    (base/"annotations"/f"{did.lower()}.json").write_text(json.dumps(ann,indent=2,ensure_ascii=False),encoding="utf-8")

manifest = {
    "name":"SuperDocs Public Golden Corpus",
    "version":"0.1.0",
    "purpose":"Licence-clean, redistributable synthetic document corpus for testing document ingestion, attachments and export.",
    "document_count":len(docs),
    "license_policy":"All corpus documents are original synthetic material released under CC0 1.0.",
    "documents":[json.loads(p.read_text()) for p in sorted((base/"annotations").glob("*.json"))]
}
(base/"MANIFEST.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")

(base/"LICENSES.md").write_text("""# Licensing

All documents in this corpus are original synthetic material created specifically for the SuperDocs evaluation.

- Corpus documents: **CC0 1.0 Universal**
- No third-party documents, private files, employer material, or proprietary assets are included.
- Every document has a per-document annotation recording its source and licence.
- `license.verified: true` means the material is self-authored and therefore does not depend on a third-party redistribution permission.

CC0 reference: https://creativecommons.org/publicdomain/zero/1.0/
""",encoding="utf-8")

(base/"LICENSE").write_text("""MIT License

Copyright (c) 2026 SuperDocs Round 2 Candidate

Permission is hereby granted, free of charge, to any person obtaining a copy
of the validation scripts and other code in this repository, to use, copy,
modify, merge, publish, distribute, sublicense, and/or sell copies of the
code, subject to the conditions of the MIT License.

THE CODE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
""",encoding="utf-8")
