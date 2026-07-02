import React, { useCallback, useEffect, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  ReactFlowProvider,
  Node,
  Edge,
  Handle,
  Position,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  MiniMap
} from "reactflow";
import "reactflow/dist/style.css";

type GraphPayload = {
  topology: {
    nodes: { name: string, attributes: { name: string, data_type: string, is_key: "PK" | "FK" | "none" }[] }[];
    edges: {
      source: string;
      target: string;
      relationship?: string;
      cardinality_or_type: string;
    }[];
  };
  actions: {
    entity_name: string;
    attribute_name: string | null;
    status: "highlight" | "error" | "dim"
  }[];

  edges?: {
    source: string;
    target: string;
    status: "highlight" | "error" | "dim";
  }[];

};

const statusClasses = {
  normal: {
    border: "border-[#00cccc]",
    header: "bg-[#00cccc]/70",
    opacity: "opacity-100",
  },

  highlight: {
    border: "border-emerald-500",
    header: "bg-emerald-700",
    opacity: "opacity-100",
  },

  error: {
    border: "border-red-500",
    header: "bg-red-950/40",
    opacity: "opacity-100",
  },

  dim: {
    border: "border-slate-700",
    header: "bg-slate-900",
    opacity: "opacity-30",
  },
};

function SchemaEntityNode({ data }: any) {

  const styles = statusClasses[data.tableStatus as keyof typeof statusClasses] ??
    statusClasses.normal;
  return (
    <div
      className={`
        min-w-65
        overflow-hidden
        rounded-xl
        border
        bg-black
        shadow-lg
        transition-all
        duration-300
        ${styles.border}
        ${styles.opacity}
      `}
    >

      {/* Entity Header */}
      <div
        className={`
          border-b
          px-3
          py-2
          ${styles.header}
        `}
      >
        <div className="text-sm font-light tracking-widest text-cyan-200">
          {data.name}
        </div>
      </div>

      {/* Attributes */}
      <div className="divide-y divide-slate-700">
        {data.attributes?.map((attr: any) => {
          const attrStatus = data.attributeActionMap?.get(`${data.name}:${attr.name}`) ?? "normal";

          const attrRowClass = attrStatus === "highlight" ? "bg-green-500/20"
            : attrStatus === "error"
              ? "bg-red-500/20"
              : attrStatus === "dim"
                ? "opacity-40"
                : "";
          // console.log(`entity_name:${data.name}, attr_name: ${attr.name}, edge: ${data.attributeActionMap.get(`${data.name}:${attr.name}`)}`);
          return (
            <div
              key={attr.name}
              className={`flex items-center justify-between px-3 py-2 text-xs transition-all duration-300 ${attrRowClass}`}
            >
              <div className="flex items-center gap-2">
                {attr.is_key === "PK" && (
                  <span className="font-bold text-yellow-400">
                    PK
                  </span>
                )}

                {attr.is_key === "FK" && (
                  <span className="font-bold text-green-400">
                    FK
                  </span>
                )}

                <span className="text-slate-200">
                  {attr.name}
                </span>
              </div>

              <span className="text-slate-500">
                {attr.data_type}
              </span>
            </div>
          )
        })}
      </div>

      <Handle
        type="target"
        position={Position.Left}
        className="bg-cyan-400"
      />

      <Handle
        type="source"
        position={Position.Right}
        className="bg-cyan-400"
      />
    </div>
  );
}

const nodeTypes = {
  entityNode: SchemaEntityNode
};

function SchemaCanvasInner({ graphPayload }: { graphPayload: GraphPayload }) {

  const { tableActionMap, attributeActionMap } = useMemo(() => {
    const tableActionMap = new Map();
    const attributeActionMap = new Map();

    for (const action of graphPayload.actions ?? []) {
      if (!action.attribute_name) {
        tableActionMap.set(
          action.entity_name,
          action.status
        );
      } else {
        attributeActionMap.set(
          `${action.entity_name}:${action.attribute_name}`,
          action.status
        );
      }
    }

    return {
      tableActionMap,
      attributeActionMap,
    };
  }, [graphPayload.actions]);


  const initialNodes: Node[] = useMemo(() => {
    return graphPayload.topology.nodes.map((n, idx) => {
      return {
        id: n.name,

        type: "entityNode",

        position: {
          x: (idx % 3) * 340,
          y: Math.floor(idx / 3) * 260,
        },

        data: {
          name: n.name,
          attributes: n.attributes ?? [],
          tableStatus: tableActionMap.get(n.name) ?? "normal",
          attributeActionMap
        },
      }
    });
  }, [graphPayload.topology.nodes, tableActionMap, attributeActionMap]);


  const edgeActionMap = useMemo(() => {
    const map = new Map();

    for (const edge of graphPayload.edges ?? []) {
      map.set(
        `${edge.source}->${edge.target}`,
        edge.status
      );
    }
    return map;
  }, [graphPayload.edges]);

  const initialEdges: Edge[] = useMemo(() => {

    return graphPayload.topology.edges.map((e, idx) => {

      const edgeStatus = edgeActionMap.get(`${e.source}->${e.target}`) ?? "normal";

      
      const edgeStyle =
        edgeStatus === "highlight"
          ? {
            stroke: "oklch(76.5% 0.177 163.223)",
            strokeWidth: 3,
          }
          : edgeStatus === "error"
            ? {
              stroke: "#ef4444",
              strokeWidth: 3,
            }
            : edgeStatus === "dim"
              ? {
                stroke: "#475569",
                strokeWidth: 1,
              }
              : {
                stroke: "#00cccc",
                strokeWidth: 1.8,
              };

      return {
        id: `e-${idx}`,
        source: e.source,
        target: e.target,
        label: e.cardinality_or_type,



        style: {
          ...edgeStyle,
          strokeDasharray: "6 6",
        },

        //   strokeDasharray: isForiegnKeyRelationship ? "6 6" : "",
        //   stroke: isForiegnKeyRelationship ? "#64748b" : "",
        //   strokeWidth: isForiegnKeyRelationship ? 2 : 1.8,

        animated: true,

        labelStyle: {
          fontSize: 11,
          fill: "#67e8f9",
        },

        labelBgStyle: {
          fill: "transparent",
        },

      }
    });
  }, [graphPayload.topology.edges, edgeActionMap]);


  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  
  const onConnect = useCallback( // connecting edges
    (connection: any) => setEdges((eds) => addEdge(connection, eds)),
  [setEdges])

  useEffect(() => {
    setNodes(initialNodes)
  }, [initialNodes, setNodes])

  useEffect(() => {
    setEdges(initialEdges)
  }, [initialEdges, setEdges])
  return (
    <div className="h-full w-full ">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        fitView
        nodesDraggable={true}
        elementsSelectable={true}
        panOnDrag={true}
        onConnect={onConnect}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={18}
          size={1.5}
          className="bg-black"
        />

        <MiniMap />
        <Controls />
      </ReactFlow>
    </div>
  );
}

export default function InteractiveSchemaCanvas({
  graphPayload,
}: {
  graphPayload: GraphPayload;
}) {
  if (!graphPayload?.topology?.nodes?.length) return null;

  return (
    <div className="h-full w-full">
      <ReactFlowProvider>
        <SchemaCanvasInner graphPayload={graphPayload} />
      </ReactFlowProvider>
    </div>
  );
}