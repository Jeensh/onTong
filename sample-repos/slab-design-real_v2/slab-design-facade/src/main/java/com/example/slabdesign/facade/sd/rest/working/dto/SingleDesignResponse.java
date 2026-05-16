package com.example.slabdesign.facade.sd.rest.working.dto;

import com.example.slabdesign.feature.sd.trace.StepTrace;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;

import java.util.List;

public record SingleDesignResponse(
    List<SDSlabEntity> slabResults,
    String errorCode,
    String errorMessage,
    List<StepTrace> trace
) {
    public static SingleDesignResponse ok(List<SDSlabEntity> slabs) {
        return new SingleDesignResponse(slabs, null, null, null);
    }
    public static SingleDesignResponse okWithTrace(List<SDSlabEntity> slabs, List<StepTrace> trace) {
        return new SingleDesignResponse(slabs, null, null, trace);
    }
    public static SingleDesignResponse fail(String code, String message, List<StepTrace> trace) {
        return new SingleDesignResponse(List.of(), code, message, trace);
    }
}
