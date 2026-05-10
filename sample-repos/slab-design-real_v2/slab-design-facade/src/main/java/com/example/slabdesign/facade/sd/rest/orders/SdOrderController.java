package com.example.slabdesign.facade.sd.rest.orders;

import com.example.slabdesign.facade.sd.rest.orders.dto.OrderDetail;
import com.example.slabdesign.facade.sd.rest.orders.dto.OrderSummary;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOmJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderPK;
import com.example.slabdesign.store.sd.working.repository.SDOrderChemicalRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderOmRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderOsRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderQdRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.data.domain.PageRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

import java.util.List;

/**
 * 주문 데이터 브라우징 — 시드된 ORDER_OS/OM/QD/CHEMICAL 의 read-only 진입점.
 */
@RestController
@RequestMapping("/api/sd/orders")
@Tag(name = "Orders", description = "Seeded order browsing")
public class SdOrderController {

    private final SDOrderOsRepository osRepo;
    private final SDOrderOmRepository omRepo;
    private final SDOrderQdRepository qdRepo;
    private final SDOrderChemicalRepository chemRepo;

    public SdOrderController(SDOrderOsRepository osRepo,
                             SDOrderOmRepository omRepo,
                             SDOrderQdRepository qdRepo,
                             SDOrderChemicalRepository chemRepo) {
        this.osRepo = osRepo;
        this.omRepo = omRepo;
        this.qdRepo = qdRepo;
        this.chemRepo = chemRepo;
    }

    @Operation(summary = "회사·소 단위 주문 목록 (페이지)")
    @GetMapping
    public List<OrderSummary> list(
            @RequestParam String cmpCd,
            @RequestParam String orgCd,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return osRepo.findByCmpCdAndOrgCd(cmpCd, orgCd, PageRequest.of(page, size))
            .stream().map(this::toSummary).toList();
    }

    @Operation(summary = "주문 1건 상세 — OS/OM/QD/CHEMICAL 4종 결합")
    @GetMapping("/{cmpCd}/{orgCd}/{orderNo}")
    public OrderDetail detail(@PathVariable String cmpCd,
                              @PathVariable String orgCd,
                              @PathVariable String orderNo) {
        SDOrderPK pk = new SDOrderPK(cmpCd, orgCd, orderNo);
        return new OrderDetail(
            osRepo.findById(pk).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "ORDER_OS not found: " + orderNo)),
            omRepo.findById(pk).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "ORDER_OM not found: " + orderNo)),
            qdRepo.findById(pk).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "ORDER_QD not found: " + orderNo)),
            chemRepo.findById(pk).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "ORDER_CHEMICAL not found: " + orderNo))
        );
    }

    /**
     * OS row 를 받아 OM 을 곁따라 조회 → OrderSummary 빌드.
     * productCd / orderWidth / orderLength 는 ORDER_OM, confirmedPlantCd 는 ORDER_OS 출처.
     * OM 누락 시 해당 필드는 null.
     */
    private OrderSummary toSummary(SDOrderOsJpo os) {
        SDOrderPK pk = new SDOrderPK(os.getCmpCd(), os.getOrgCd(), os.getOrderNo());
        SDOrderOmJpo om = omRepo.findById(pk).orElse(null);
        return new OrderSummary(
            os.getCmpCd(),
            os.getOrgCd(),
            os.getOrderNo(),
            om == null ? null : om.getProductCd(),
            os.getConfirmedPlantCd(),
            om == null ? null : om.getOrderWidth(),
            om == null ? null : om.getOrderLength()
        );
    }
}
