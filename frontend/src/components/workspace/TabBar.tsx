"use client";

import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  horizontalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { X } from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import type { Tab } from "@/types";

function SortableTab({ tab, isActive }: { tab: Tab; isActive: boolean }) {
  const { closeTab, setActiveTab } = useWorkspaceStore();
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: tab.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`group flex items-center gap-1.5 px-3 py-1.5 text-sm cursor-pointer border-b-2 select-none shrink-0 ${
        isActive
          ? "border-primary bg-background text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50"
      }`}
      onClick={() => setActiveTab(tab.id)}
    >
      <span className="truncate max-w-[120px]">
        {tab.isDirty && <span className="text-orange-500 mr-1">●</span>}
        {tab.title}
      </span>
      <button
        className="ml-1 rounded-sm opacity-0 group-hover:opacity-100 hover:bg-muted p-0.5"
        onClick={(e) => {
          e.stopPropagation();
          closeTab(tab.id);
        }}
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}

export function TabBar() {
  const { tabs, activeTabId, reorderTabs } = useWorkspaceStore();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const fromIndex = tabs.findIndex((t) => t.id === active.id);
    const toIndex = tabs.findIndex((t) => t.id === over.id);
    if (fromIndex !== -1 && toIndex !== -1) {
      reorderTabs(fromIndex, toIndex);
    }
  }

  if (tabs.length === 0) return null;

  return (
    <div className="flex items-center border-b bg-muted/30 overflow-x-auto">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={tabs.map((t) => t.id)}
          strategy={horizontalListSortingStrategy}
        >
          {tabs.map((tab) => (
            <SortableTab
              key={tab.id}
              tab={tab}
              isActive={tab.id === activeTabId}
            />
          ))}
        </SortableContext>
      </DndContext>
    </div>
  );
}
