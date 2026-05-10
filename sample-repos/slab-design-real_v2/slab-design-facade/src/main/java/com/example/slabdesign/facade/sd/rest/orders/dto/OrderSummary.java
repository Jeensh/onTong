package com.example.slabdesign.facade.sd.rest.orders.dto;

import java.math.BigDecimal;

/**
 * 주문 목록용 요약 DTO.
 * cmpCd/orgCd/orderNo/confirmedPlantCd 는 ORDER_OS, productCd/orderWidth/orderLength 는 ORDER_OM 출처.
 */
public record OrderSummary(
    String cmpCd,
    String orgCd,
    String orderNo,
    String productCd,
    String confirmedPlantCd,
    BigDecimal orderWidth,
    BigDecimal orderLength
) {}
