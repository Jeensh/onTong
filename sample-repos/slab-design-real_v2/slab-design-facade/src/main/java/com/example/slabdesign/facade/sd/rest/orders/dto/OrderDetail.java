package com.example.slabdesign.facade.sd.rest.orders.dto;

import com.example.slabdesign.store.sd.working.jpo.SDOrderChemicalJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOmJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderQdJpo;

/**
 * 주문 상세 DTO — 4 JPO (OS/OM/QD/CHEMICAL) 를 그대로 묶어 반환.
 */
public record OrderDetail(
    SDOrderOsJpo os,
    SDOrderOmJpo om,
    SDOrderQdJpo qd,
    SDOrderChemicalJpo chemical
) {}
