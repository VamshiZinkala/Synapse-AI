import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ASSETS_DIR = r"c:\synapseAi\Synapse-AI\report_assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

def generate_all_figures():
    # -------------------------------------------------------------
    # 1. Figure 3.1: 4-Tier Architecture Diagram
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 4.5), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis('off')

    tiers = [
        ("Tier 1: Presentation & Interactive Cockpit", "Next.js 15 • React 19 • React Flow • SSE Streaming • Dual-Pane Canvas", 4.75, "#EFF6FF", "#3B82F6"),
        ("Tier 2: Stateful Multi-Agent Orchestration", "FastAPI • LangGraph Cyclic StateGraph • Conditional Tool Routing • AsyncPostgresSaver", 3.45, "#F0FDF4", "#10B981"),
        ("Tier 3: Multi-Modal Ingestion & Tooling", "PyMuPDF • Vision-Language Models (VLM) • Diagram Reasoning Agent • Model Context Protocol (MCP)", 2.15, "#FEF3C7", "#F59E0B"),
        ("Tier 4: Relational & Vector Storage Layer", "PostgreSQL 16 • pgvector (HNSW Indexing) • SQLAlchemy Async ORM • Alembic Migrations", 0.85, "#F5F3FF", "#8B5CF6")
    ]

    for title, desc, y, bg_col, bdr_col in tiers:
        rect = patches.FancyBboxPatch((0.5, y), 9.0, 1.0, boxstyle="round,pad=0.15", facecolor=bg_col, edgecolor=bdr_col, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(0.8, y + 0.65, title, fontsize=11, fontweight='bold', color='#0F172A', va='center')
        ax.text(0.8, y + 0.25, desc, fontsize=8.5, color='#334155', va='center')

    # Draw vertical arrows between tiers
    for y_arrow in [4.65, 3.35, 2.05]:
        ax.annotate('', xy=(5.0, y_arrow - 0.2), xytext=(5.0, y_arrow + 0.1),
                    arrowprops=dict(arrowstyle="<->", color="#64748B", lw=1.5))

    plt.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "fig_arch_diagram.png"), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    # -------------------------------------------------------------
    # 2. Figure 3.2: LangGraph State Machine Flow
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 3.6), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis('off')

    nodes = [
        ("START", 0.8, 2.0, "#E2E8F0", "#475569"),
        ("chat_node\n(LLM + Tools)", 2.8, 2.0, "#DBEAFE", "#2563EB"),
        ("route_chat\n(Router)", 5.2, 2.0, "#FEF08A", "#CA8A04"),
        ("ToolNode\n(MCP / RAG)", 5.2, 0.6, "#DCFCE7", "#16A34A"),
        ("summarize\n(Compressor)", 7.6, 2.0, "#F3E8FF", "#9333EA"),
        ("END", 9.4, 2.0, "#E2E8F0", "#475569")
    ]

    for text, x, y, bg, bdr in nodes:
        w, h = (1.5, 0.9) if "chat_node" in text or "ToolNode" in text or "summarize" in text else (1.0, 0.7)
        rect = patches.FancyBboxPatch((x - w/2, y - h/2), w, h, boxstyle="round,pad=0.1", facecolor=bg, edgecolor=bdr, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x, y, text, fontsize=8.5, fontweight='bold', color='#0F172A', ha='center', va='center')

    # Connections
    ax.annotate('', xy=(2.0, 2.0), xytext=(1.35, 2.0), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    ax.annotate('', xy=(4.65, 2.0), xytext=(3.6, 2.0), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    ax.annotate('', xy=(5.2, 1.1), xytext=(5.2, 1.55), arrowprops=dict(arrowstyle="->", color="#16A34A", lw=1.5))
    ax.text(5.5, 1.3, "tool_calls", fontsize=7.5, color="#16A34A", fontweight='bold')
    
    # Tool return arrow back to chat_node
    ax.annotate('', xy=(2.8, 1.5), xytext=(4.4, 0.6), arrowprops=dict(arrowstyle="->", color="#2563EB", lw=1.5, connectionstyle="arc3,rad=-0.2"))
    ax.text(3.3, 0.8, "tool_output", fontsize=7.5, color="#2563EB")

    # route to summarize
    ax.annotate('', xy=(6.8, 2.0), xytext=(5.75, 2.0), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    ax.text(6.2, 2.2, "no tools", fontsize=7.5, color="#475569")

    # summarize to END
    ax.annotate('', xy=(8.85, 2.0), xytext=(8.4, 2.0), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))

    plt.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "fig_langgraph_flow.png"), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    # -------------------------------------------------------------
    # 3. Figure 4.2: Automated Diagram Reasoning & Diff Pipeline
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 3.6), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis('off')

    steps = [
        ("Raw Image /\nPDF Schematic", 1.0, 2.0, "#F1F5F9", "#64748B"),
        ("VLM Extractor\n(Pydantic Graph)", 3.2, 2.0, "#DBEAFE", "#2563EB"),
        ("Reasoning Agent\n(Audit Rules)", 5.5, 2.0, "#FEF3C7", "#D97706"),
        ("Atomic Diff Engine\n(add / remove op)", 7.8, 2.0, "#DCFCE7", "#16A34A")
    ]

    for text, x, y, bg, bdr in steps:
        rect = patches.FancyBboxPatch((x - 0.9, y - 0.55), 1.8, 1.1, boxstyle="round,pad=0.1", facecolor=bg, edgecolor=bdr, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x, y, text, fontsize=8.5, fontweight='bold', color='#0F172A', ha='center', va='center')

    # Horizontal arrows
    ax.annotate('', xy=(2.25, 2.0), xytext=(1.95, 2.0), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    ax.annotate('', xy=(4.55, 2.0), xytext=(4.15, 2.0), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    ax.annotate('', xy=(6.85, 2.0), xytext=(6.45, 2.0), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))

    # Bottom output: Accepted -> DiagramVersion
    rect_out = patches.FancyBboxPatch((3.5, 0.2), 3.5, 0.7, boxstyle="round,pad=0.1", facecolor="#F5F3FF", edgecolor="#8B5CF6", linewidth=1.5)
    ax.add_patch(rect_out)
    ax.text(5.25, 0.55, "Dual-Pane Canvas & Immutable DiagramVersion Commit", fontsize=8.5, fontweight='bold', color='#5B21B6', ha='center', va='center')
    ax.annotate('', xy=(5.25, 0.95), xytext=(7.8, 1.4), arrowprops=dict(arrowstyle="->", color="#8B5CF6", lw=1.5, connectionstyle="arc3,rad=0.2"))

    plt.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "fig_diagram_reasoning.png"), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    # -------------------------------------------------------------
    # 4. Figure 5.1: Latency & Throughput Benchmark Chart
    # -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.5, 3.4), dpi=200)

    modules = ['VLM Extract', 'Graph Route', 'MCP Dispatch', 'HNSW Vector', 'Reasoning Diff', 'Version Commit']
    latencies = [640, 12, 45, 6.8, 820, 18]
    colors_lat = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EF4444', '#06B6D4']

    bars = ax1.barh(modules, latencies, color=colors_lat, height=0.6)
    ax1.set_xlabel('Average Execution Latency (ms)', fontsize=9, fontweight='bold', color='#0F172A')
    ax1.set_title('Operational Latency by Node', fontsize=10, fontweight='bold', color='#0F172A')
    ax1.grid(axis='x', linestyle='--', alpha=0.6)
    for bar in bars:
        ax1.text(bar.get_width() + 15, bar.get_y() + bar.get_height()/2, f'{bar.get_width()} ms',
                 va='center', fontsize=7.5, color='#334155')
    ax1.set_xlim(0, 950)

    # Recall vs Index
    indices = ['Flat (IVFFlat)', 'HNSW (m=16)', 'HNSW (m=32)']
    recalls = [91.4, 98.9, 99.6]
    query_times = [48.5, 6.8, 8.1]

    ax2_twin = ax2.twinx()
    b1 = ax2.bar([0, 1, 2], recalls, width=0.35, color='#3B82F6', label='Top-10 Recall (%)', align='center')
    p1 = ax2_twin.plot([0, 1, 2], query_times, color='#EF4444', marker='o', linewidth=2, label='Query Time (ms)')

    ax2.set_xticks([0, 1, 2])
    ax2.set_xticklabels(indices, fontsize=8)
    ax2.set_ylim(85, 102)
    ax2.set_ylabel('Recall Accuracy (%)', fontsize=8.5, fontweight='bold', color='#1D4ED8')
    ax2_twin.set_ylabel('Latency (ms)', fontsize=8.5, fontweight='bold', color='#B91C1C')
    ax2.set_title('Vector Search Recall vs. Latency', fontsize=10, fontweight='bold', color='#0F172A')

    plt.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "fig_latency_breakdown.png"), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    # -------------------------------------------------------------
    # 5. Figure 6.1: ATM Sequence Correction Flow
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 3.6), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis('off')

    # Top: Flawed Flow
    ax.text(0.5, 3.4, "Flawed Sequence (Detected Anti-Pattern):", fontsize=9.5, fontweight='bold', color='#B91C1C')
    flawed_boxes = [("Insert Card", 1.5, 2.7, "#F1F5F9"), ("Dispense Cash [CRITICAL ERROR]", 4.5, 2.7, "#FEE2E2"), ("Enter PIN", 7.5, 2.7, "#F1F5F9")]
    for t, x, y, bg in flawed_boxes:
        w = 2.4 if "CRITICAL" in t else 1.8
        rect = patches.FancyBboxPatch((x - w/2, y - 0.35), w, 0.7, boxstyle="round,pad=0.1", facecolor=bg, edgecolor="#EF4444" if "CRITICAL" in t else "#94A3B8")
        ax.add_patch(rect)
        ax.text(x, y, t, fontsize=7.5, fontweight='bold', color='#991B1B' if "CRITICAL" in t else '#0F172A', ha='center', va='center')
    ax.annotate('', xy=(3.15, 2.7), xytext=(2.45, 2.7), arrowprops=dict(arrowstyle="->", color="#EF4444", lw=1.5))
    ax.annotate('', xy=(6.45, 2.7), xytext=(5.85, 2.7), arrowprops=dict(arrowstyle="->", color="#EF4444", lw=1.5))

    # Bottom: Corrected Flow
    ax.text(0.5, 1.8, "Synapse-AI Verified Flow (Version 2.0 Accepted):", fontsize=9.5, fontweight='bold', color='#15803D')
    corr_boxes = [("Insert Card", 1.2, 0.9, "#DCFCE7"), ("Card Valid?", 3.2, 0.9, "#FEF08A"), ("Enter PIN", 5.2, 0.9, "#DCFCE7"), ("PIN Correct?", 7.2, 0.9, "#FEF08A"), ("Dispense Cash", 9.0, 0.9, "#DCFCE7")]
    for t, x, y, bg in corr_boxes:
        rect = patches.FancyBboxPatch((x - 0.75, y - 0.35), 1.5, 0.7, boxstyle="round,pad=0.1", facecolor=bg, edgecolor="#16A34A" if "DCFCE7" in bg else "#CA8A04")
        ax.add_patch(rect)
        ax.text(x, y, t, fontsize=7.5, fontweight='bold', color='#0F172A', ha='center', va='center')
    for ax_start, ax_end in [(2.0, 2.4), (4.0, 4.4), (6.0, 6.4), (8.0, 8.2)]:
        ax.annotate('', xy=(ax_end, 0.9), xytext=(ax_start, 0.9), arrowprops=dict(arrowstyle="->", color="#15803D", lw=1.5))

    plt.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "fig_atm_case_study.png"), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    print("All 5 diagram figures successfully generated in:", ASSETS_DIR)

if __name__ == "__main__":
    generate_all_figures()

