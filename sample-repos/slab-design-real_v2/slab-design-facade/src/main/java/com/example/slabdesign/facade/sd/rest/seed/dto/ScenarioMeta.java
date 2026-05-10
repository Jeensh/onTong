package com.example.slabdesign.facade.sd.rest.seed.dto;

public record ScenarioMeta(
    String id,                  // S1..S5
    String orderNo,
    String description,
    String confirmedPlantCd,
    String expectedOutcome      // "1 slab", "4 slabs", "DG004 fail", ...
) {}
