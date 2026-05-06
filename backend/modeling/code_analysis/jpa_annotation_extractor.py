"""OD-11-B6-4 companion — JPA annotation extractor.

Merges @Entity / @Table / @Column / @Id / @IdClass / @JoinColumn info into
class CodeEntity.attributes:
  - jpa_entity_name : @Entity(name=...) value or class simple name (fallback)
  - jpa_table       : @Table(name=...) value (lowercase) or None
  - jpa_columns     : {field_name: column_name.lower()}     ← legacy, backward-compat
  - jpa_columns_meta: {field_name: {name, length, precision, scale, nullable, is_id, join_target}}
                      ← P0.2 (2026-04-25) full @Column metadata for impact analysis
  - jpa_id_class    : @IdClass(X.class) → "X" (composite PK class simple name)
  - jpa_id_fields   : [field_name, ...] of @Id-annotated fields (composite key)

Design:
  - Operates on already-parsed CodeEntity (CLASS + FIELDs). Reads
    `attributes["annotations"]` populated by the Java parser (P0.1).
  - Annotation entries are dicts `{name, arguments}`.  Legacy string entries
    (no arguments) still accepted.
  - CodeEntity is frozen but its `attributes` dict is mutable; merge writes
    happen in-place on the dict.

Spec: toClaude/modeling/OD-11-B6-SPEC.md §6.2 (Q2 Option C — separate module).
"""
from __future__ import annotations

from backend.modeling.code_analysis.parser_protocol import CodeEntity

_ENTITY_ANNOS = frozenset(
    {"Entity", "javax.persistence.Entity", "jakarta.persistence.Entity"}
)
_TABLE_ANNOS = frozenset(
    {"Table", "javax.persistence.Table", "jakarta.persistence.Table"}
)
_COLUMN_ANNOS = frozenset(
    {"Column", "javax.persistence.Column", "jakarta.persistence.Column"}
)
_JOIN_COLUMN_ANNOS = frozenset(
    {"JoinColumn", "javax.persistence.JoinColumn", "jakarta.persistence.JoinColumn"}
)
_ID_ANNOS = frozenset(
    {"Id", "javax.persistence.Id", "jakarta.persistence.Id"}
)
_ID_CLASS_ANNOS = frozenset(
    {"IdClass", "javax.persistence.IdClass", "jakarta.persistence.IdClass"}
)


class JpaAnnotationExtractor:
    """Extract JPA annotations into class CodeEntity.attributes."""

    def merge_into(
        self, class_entity: CodeEntity, fields: list[CodeEntity]
    ) -> None:
        """Merge @Entity/@Table/@Column/@Id/@IdClass info into class_entity.attributes.

        Respects keys already present (does not overwrite).
        """
        annos = class_entity.attributes.get("annotations") or []
        entity_name = self._extract_entity_name(annos, class_entity.name)
        table_name = self._extract_table_name(annos)
        id_class = self._extract_id_class(annos)
        column_map, column_meta, id_fields = self._extract_column_data(fields)

        class_entity.attributes.setdefault("jpa_entity_name", entity_name)
        class_entity.attributes.setdefault("jpa_table", table_name)
        class_entity.attributes.setdefault("jpa_columns", column_map)
        class_entity.attributes.setdefault("jpa_columns_meta", column_meta)
        class_entity.attributes.setdefault("jpa_id_fields", id_fields)
        if id_class is not None:
            class_entity.attributes.setdefault("jpa_id_class", id_class)

    def _anno_name(self, anno: object) -> str:
        if isinstance(anno, str):
            return anno
        if isinstance(anno, dict):
            return str(anno.get("name", ""))
        return ""

    def _anno_args(self, anno: object) -> dict[str, object]:
        if isinstance(anno, dict):
            args = anno.get("arguments")
            if isinstance(args, dict):
                return args
        return {}

    def _arg_str(self, arg: object) -> str | None:
        if isinstance(arg, str):
            cleaned = arg.strip().strip('"')
            return cleaned or None
        return None

    def _extract_entity_name(self, annos: list, default_name: str) -> str:
        for anno in annos:
            name = self._anno_name(anno)
            simple = name.rsplit(".", 1)[-1]
            if simple == "Entity" or name in _ENTITY_ANNOS:
                explicit = self._arg_str(self._anno_args(anno).get("name"))
                if explicit:
                    return explicit
                return default_name
        return default_name

    def _extract_table_name(self, annos: list) -> str | None:
        for anno in annos:
            name = self._anno_name(anno)
            simple = name.rsplit(".", 1)[-1]
            if simple == "Table" or name in _TABLE_ANNOS:
                explicit = self._arg_str(self._anno_args(anno).get("name"))
                if explicit:
                    return explicit.lower()
        return None

    def _extract_column_map(
        self, fields: list[CodeEntity]
    ) -> dict[str, str]:
        # legacy backward-compat path — delegates to richer _extract_column_data.
        column_map, _, _ = self._extract_column_data(fields)
        return column_map

    def _extract_column_data(
        self, fields: list[CodeEntity]
    ) -> tuple[dict[str, str], dict[str, dict], list[str]]:
        """Walk fields once → (column_map, column_meta, id_fields)."""
        column_map: dict[str, str] = {}
        column_meta: dict[str, dict] = {}
        id_fields: list[str] = []

        for f in fields:
            annos = f.attributes.get("annotations") or []
            is_id = self._has_id_annotation(annos)
            if is_id:
                id_fields.append(f.name)

            for anno in annos:
                name = self._anno_name(anno)
                simple = name.rsplit(".", 1)[-1]
                if simple == "Column" or name in _COLUMN_ANNOS:
                    args = self._anno_args(anno)
                    col_name_raw = self._arg_str(args.get("name"))
                    if not col_name_raw:
                        continue
                    column_map[f.name] = col_name_raw.lower()
                    column_meta[f.name] = self._build_column_meta(
                        col_name_raw, args, is_id, join_target=None,
                    )
                    break
                if simple == "JoinColumn" or name in _JOIN_COLUMN_ANNOS:
                    args = self._anno_args(anno)
                    col_name_raw = self._arg_str(args.get("name"))
                    if not col_name_raw:
                        continue
                    column_map.setdefault(f.name, col_name_raw.lower())
                    join_target = self._arg_str(args.get("referencedColumnName"))
                    column_meta.setdefault(
                        f.name,
                        self._build_column_meta(
                            col_name_raw, args, is_id, join_target=join_target,
                        ),
                    )
                    break
        return column_map, column_meta, id_fields

    @staticmethod
    def _build_column_meta(
        name_raw: str, args: dict, is_id: bool, *, join_target: str | None,
    ) -> dict:
        meta: dict = {"name": name_raw, "name_lower": name_raw.lower(), "is_id": is_id}
        for key in ("length", "precision", "scale"):
            v = args.get(key)
            if isinstance(v, int):
                meta[key] = v
        nullable = args.get("nullable")
        if isinstance(nullable, bool):
            meta["nullable"] = nullable
        unique = args.get("unique")
        if isinstance(unique, bool):
            meta["unique"] = unique
        if join_target:
            meta["join_target_column"] = join_target.lower()
        return meta

    def _has_id_annotation(self, annos: list) -> bool:
        for anno in annos:
            name = self._anno_name(anno)
            simple = name.rsplit(".", 1)[-1]
            if simple == "Id" or name in _ID_ANNOS:
                return True
        return False

    def _extract_id_class(self, annos: list) -> str | None:
        for anno in annos:
            name = self._anno_name(anno)
            simple = name.rsplit(".", 1)[-1]
            if simple == "IdClass" or name in _ID_CLASS_ANNOS:
                args = self._anno_args(anno)
                # @IdClass(HrSpecPK.class) → arguments == {"value": "HrSpecPK.class"}
                raw = args.get("value")
                if isinstance(raw, str) and raw.endswith(".class"):
                    return raw[: -len(".class")]
                if isinstance(raw, str) and raw:
                    return raw
        return None


__all__ = ["JpaAnnotationExtractor"]
