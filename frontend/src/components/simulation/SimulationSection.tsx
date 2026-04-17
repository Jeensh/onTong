"use client";

import { useEffect, useCallback } from "react";
import { useSimulationStore } from "@/lib/simulation/useSimulationStore";
import { fetchOntologyGraph, fetchOrders, fetchCustomAgents } from "@/lib/simulation/api";
import { OntologyGraph } from "./OntologyGraph";
import { ChatPanel } from "./ChatPanel";
import { SlabSizeSimulator } from "./SlabSizeSimulator";
import { SimulationSidebar } from "./SimulationSidebar";
import { CustomAgentHub } from "./CustomAgentHub";
import { AgentBuilderChat } from "./AgentBuilderChat";
import { CustomAgentRunner } from "./CustomAgentRunner";
import { CustomAgentFormBuilder } from "./CustomAgentFormBuilder";
import type { OntologyNode } from "@/lib/simulation/types";
import type { SlabSizeParams } from "@/lib/simulation/types";

export function SimulationSection() {
  const {
    graphData,
    graphHighlight,
    setGraphData,
    setOrders,
    activeView,
    activeScenario,
    setActiveScenario,
    orders,
    setPendingSlabParams,
    setCustomAgents,
  } = useSimulationStore();

  // 앱 시작 시 주문 + 커스텀 에이전트 목록 로드
  useEffect(() => {
    fetchOrders().then(setOrders).catch(console.error);
    fetchCustomAgents().then(setCustomAgents).catch(console.error);
  }, [setOrders, setCustomAgents]);

  // 온톨로지 그래프는 A/B/C 시나리오에서만 로드
  useEffect(() => {
    if (activeView.kind !== "scenario") return;
    if (activeView.id === "SLAB_DESIGN") return;
    fetchOntologyGraph().then(setGraphData).catch(console.error);
  }, [setGraphData, activeView]);

  // OntologyGraph Order 노드 클릭 → Slab 설계 딥링크
  const handleOntologyNodeClick = useCallback(
    (node: OntologyNode) => {
      if (node.type !== "Order") return;
      const order = orders.find((o) => o.order_id === node.id);
      if (!order) return;
      const params: SlabSizeParams = {
        target_width: order.target_width,
        thickness: 250,
        target_length: order.target_length,
        unit_weight: order.slab_weight ?? Math.round((order.order_weight_min + order.order_weight_max) / 2),
        split_count: order.split_count ?? 2,
        yield_rate: order.yield_rate,
        assigned_rolling: order.assigned_rolling,
        assigned_caster: order.assigned_caster,
      };
      setPendingSlabParams(params);
      setActiveScenario("SLAB_DESIGN");
    },
    [orders, setPendingSlabParams, setActiveScenario]
  );

  // ── 메인 콘텐츠 렌더링 ───────────────────────────────────────────────
  const renderContent = () => {
    // 커스텀 에이전트 뷰
    if (activeView.kind === "custom_hub") {
      return <CustomAgentHub />;
    }
    if (activeView.kind === "custom_chat_builder") {
      return <AgentBuilderChat />;
    }
    if (activeView.kind === "custom_form_builder") {
      return <CustomAgentFormBuilder />;
    }
    if (activeView.kind === "custom_agent") {
      return <CustomAgentRunner agentId={activeView.agentId} />;
    }

    // 빌트인 시나리오 뷰
    if (activeView.kind === "scenario" && activeView.id === "SLAB_DESIGN") {
      return <SlabSizeSimulator />;
    }

    // 시나리오 A/B/C: 온톨로지 그래프(좌) + 채팅 패널(우)
    return (
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left: Ontology Graph */}
        <div className="w-[42%] border-r overflow-hidden">
          <OntologyGraph
            graphData={graphData}
            highlight={graphHighlight}
            onNodeClick={handleOntologyNodeClick}
          />
        </div>
        {/* Right: Chat panel */}
        <div className="flex-1 overflow-hidden">
          <ChatPanel />
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-full overflow-hidden bg-background">
      {/* 좌측 사이드바 */}
      <SimulationSidebar />

      {/* 메인 콘텐츠 */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {renderContent()}
      </div>
    </div>
  );
}
