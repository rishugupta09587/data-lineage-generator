"""
utils/export_utils.py
---------------------
Export lineage results to:
  - JSON (structured, machine-readable)
  - PDF (human-readable report using ReportLab)
"""

import json
import io
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


def export_to_json(lineage_data: Dict[str, Any]) -> bytes:
    """
    Serialize lineage result to a formatted JSON bytes object.
    Includes metadata header for traceability.
    """
    export_payload = {
        "export_metadata": {
            "tool": "Data Lineage Generator",
            "exported_at": datetime.utcnow().isoformat(),
            "version": "1.0.0",
        },
        "lineage_report": lineage_data,
    }
    return json.dumps(export_payload, indent=2, default=str).encode("utf-8")


def export_to_pdf(lineage_data: Dict[str, Any]) -> bytes:
    """
    Generate a PDF lineage report using ReportLab.
    Returns bytes that can be streamed as an HTTP response.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, HRFlowable
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()

        # ── Custom Styles ────────────────────────────────────────────
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=6,
            alignment=TA_CENTER,
        )
        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#16213e"),
            spaceBefore=16,
            spaceAfter=6,
            borderPad=4,
        )
        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#333333"),
            spaceAfter=4,
            leading=14,
        )
        mono_style = ParagraphStyle(
            "Mono",
            parent=styles["Code"],
            fontSize=9,
            textColor=colors.HexColor("#555555"),
            backColor=colors.HexColor("#f5f5f5"),
            borderPad=3,
        )

        story = []

        # ── Header ──────────────────────────────────────────────────
        story.append(Paragraph("Data Lineage Report", title_style))
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            ParagraphStyle("Sub", parent=body_style, alignment=TA_CENTER, textColor=colors.grey)
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#4f46e5")))
        story.append(Spacer(1, 12))

        # ── Query Summary ────────────────────────────────────────────
        story.append(Paragraph("Query Summary", heading_style))
        summary_data = [
            ["Field", "Value"],
            ["Query Node", lineage_data.get("query_node", "N/A")],
            ["Lineage Type", lineage_data.get("lineage_type", "N/A").upper()],
            ["Total Nodes in Result", str(lineage_data.get("node_count", 0))],
            ["Max Depth", str(lineage_data.get("depth", 0))],
            ["Computed At", str(lineage_data.get("computed_at", "N/A"))],
        ]
        summary_table = Table(summary_data, colWidths=[2.5 * inch, 4.5 * inch])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f9f9f9")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f8")]),
            ("PADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 16))

        # ── Nodes Section ────────────────────────────────────────────
        nodes = lineage_data.get("nodes", [])
        if nodes:
            story.append(Paragraph(f"Nodes in Lineage ({len(nodes)})", heading_style))
            node_data = [["ID", "Name", "Type", "Operation"]]
            for node in nodes:
                node_data.append([
                    node.get("id", ""),
                    node.get("name", node.get("id", "")),
                    node.get("type", ""),
                    node.get("operation") or "—",
                ])
            node_table = Table(node_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
            node_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e1b4b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eff6ff")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(node_table)
            story.append(Spacer(1, 16))

        # ── Edges Section ────────────────────────────────────────────
        edges = lineage_data.get("edges", [])
        if edges:
            story.append(Paragraph(f"Data Flow Edges ({len(edges)})", heading_style))
            edge_data = [["From Node", "→", "To Node", "Relationship"]]
            for edge in edges:
                edge_data.append([
                    edge.get("from_node", ""),
                    "→",
                    edge.get("to_node", ""),
                    edge.get("relationship_type") or "—",
                ])
            edge_table = Table(edge_data, colWidths=[2*inch, 0.5*inch, 2*inch, 2.5*inch])
            edge_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e1b4b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdf4")]),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ]))
            story.append(edge_table)
            story.append(Spacer(1, 16))

        # ── Paths Section ────────────────────────────────────────────
        paths = lineage_data.get("paths", [])
        if paths:
            story.append(Paragraph(f"Lineage Paths ({len(paths)})", heading_style))
            for i, path_obj in enumerate(paths[:20]):  # cap at 20 paths in PDF
                path_nodes = path_obj.get("path", [])
                path_str = " → ".join(path_nodes)
                story.append(Paragraph(
                    f"Path {i+1} (length {path_obj.get('length', len(path_nodes)-1)}): {path_str}",
                    mono_style
                ))
                story.append(Spacer(1, 4))
            if len(paths) > 20:
                story.append(Paragraph(
                    f"... and {len(paths) - 20} more paths (see JSON export for full list)",
                    body_style
                ))

        # ── Footer ───────────────────────────────────────────────────
        story.append(Spacer(1, 24))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dddddd")))
        story.append(Paragraph(
            "Data Lineage Generator — Final Year Project | Powered by NetworkX + FastAPI",
            ParagraphStyle("Footer", parent=body_style, alignment=TA_CENTER,
                          textColor=colors.grey, fontSize=8)
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer.read()

    except ImportError:
        logger.error("ReportLab not installed. Cannot generate PDF.")
        raise RuntimeError("PDF generation requires reportlab package: pip install reportlab")
