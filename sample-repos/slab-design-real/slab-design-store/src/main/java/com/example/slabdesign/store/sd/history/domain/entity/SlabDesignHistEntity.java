package com.example.slabdesign.store.sd.history.domain.entity;

import java.time.LocalDateTime;

/**
 * sd · history · SLAB_DESIGN_HIST 도메인 Entity.
 * SlabDesignHistJpo 와 1:1 미러.
 */
public class SlabDesignHistEntity {

    private String cmpCd;
    private String orgCd;
    private String histId;
    private String orderNo;
    private String slabNo;          // FAIL 시 NULL
    private Integer stepNo;
    private String stepName;
    private String errorCode;       // 성공 시 NULL
    private String snapshot;        // JSON CLOB
    private LocalDateTime eventTime;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getHistId() { return histId; }
    public void setHistId(String v) { this.histId = v; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String v) { this.orderNo = v; }
    public String getSlabNo() { return slabNo; }
    public void setSlabNo(String v) { this.slabNo = v; }
    public Integer getStepNo() { return stepNo; }
    public void setStepNo(Integer v) { this.stepNo = v; }
    public String getStepName() { return stepName; }
    public void setStepName(String v) { this.stepName = v; }
    public String getErrorCode() { return errorCode; }
    public void setErrorCode(String v) { this.errorCode = v; }
    public String getSnapshot() { return snapshot; }
    public void setSnapshot(String v) { this.snapshot = v; }
    public LocalDateTime getEventTime() { return eventTime; }
    public void setEventTime(LocalDateTime v) { this.eventTime = v; }
}
