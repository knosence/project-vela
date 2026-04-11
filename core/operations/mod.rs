use crate::events::{plan_event_append, EventRecord, ValidationSummary};
use crate::inventory::{
    discover_matrix_inventory, hub_context_for_numeric_id, hub_id_for_numeric_id,
    inferred_inventory_role_for_path, matrix_context_for_name, matrix_id_kind_for_name,
    matrix_numeric_id_for_name, matrix_subject_for_name, next_available_direct_child_id,
    next_available_grandchild_id, next_available_ref_id,
};
use crate::models::{
    ArchiveTransactionPlan, CompanionPathPlan, CrossReferencePlan, CsvInboxEntry, CsvInboxPlan,
    DimensionAppendPlan, DreamerAction, DreamerActionRegistry, DreamerApplyPlan,
    DreamerFollowUpSummary, DreamerProposalCandidate, DreamerProposalSummary, DreamerReviewPlan,
    GrowthAssessment, GrowthExecutionPlan, GrowthSourceApplyPlan, GrowthSourceUpdatePlan,
    InboxTriagePlan, MergeApplyPlan, MergeCandidateSummary, MergeFollowUpSummary,
    MergeOwnerUpdate, MergeProposalSummary, MergeReviewPlan, NightCyclePlan, OperationLifecyclePlan, OperationLockRecord,
    OperationStateEntry, OperationsState, PatrolPlan, SchedulerPlan, ValidationFinding,
};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DreamerActionMatch {
    pub pattern_reason: String,
    pub status: String,
}

pub fn default_operations_state() -> OperationsState {
    OperationsState {
        patrol: default_operation_state_entry(),
        night_cycle: default_operation_state_entry(),
    }
}

pub fn assess_growth_target(root: &Path, target: &str) -> GrowthAssessment {
    let inventory_role = inventory_role_for_growth_target(root, target);
    let path = root.join(target);
    let Ok(text) = fs::read_to_string(&path) else {
        return GrowthAssessment {
            stage: "flat".to_string(),
            reason: "Target does not exist yet, so no growth signal can be assessed.".to_string(),
            inventory_role,
            exists: false,
            line_count: 0,
            densest_dimension_entries: 0,
            has_subgroups: false,
            living_record_markers: 0,
        };
    };

    let line_count = text.lines().count();
    let densest_dimension_entries = dimension_entry_counts(&text).into_iter().max().unwrap_or(0);
    let has_subgroups = text.lines().any(is_subgroup_heading);
    let living_record_markers = [
        "### Status",
        "### Decisions",
        "### Open Questions",
        "### Next Actions",
    ]
    .into_iter()
    .map(|marker| text.matches(marker).count())
    .sum();

    if inventory_role == "cornerstone" {
        if line_count > 260 || densest_dimension_entries >= 10 {
            return GrowthAssessment {
                stage: "spawn".to_string(),
                reason: "The cornerstone should shed heavy branch detail into governed child SoTs rather than continue accumulating root complexity.".to_string(),
                inventory_role,
                exists: true,
                line_count,
                densest_dimension_entries,
                has_subgroups,
                living_record_markers,
            };
        }
        return GrowthAssessment {
            stage: "flat".to_string(),
            reason: "The cornerstone should stay as stable as possible until branch pressure clearly warrants a governed spawn.".to_string(),
            inventory_role,
            exists: true,
            line_count,
            densest_dimension_entries,
            has_subgroups,
            living_record_markers,
        };
    }

    if inventory_role == "dimension-hub" {
        if has_subgroups || densest_dimension_entries >= 8 || line_count > 220 {
            return GrowthAssessment {
                stage: "spawn".to_string(),
                reason: "A dimension hub should branch outward into child SoTs once one concern becomes dense enough to deserve its own governed home.".to_string(),
                inventory_role,
                exists: true,
                line_count,
                densest_dimension_entries,
                has_subgroups,
                living_record_markers,
            };
        }
        return GrowthAssessment {
            stage: "flat".to_string(),
            reason: "The hub remains light enough to keep collecting branch pointers without further structural change.".to_string(),
            inventory_role,
            exists: true,
            line_count,
            densest_dimension_entries,
            has_subgroups,
            living_record_markers,
        };
    }

    if inventory_role == "agent-identity" {
        if has_subgroups || densest_dimension_entries >= 10 || line_count > 240 {
            return GrowthAssessment {
                stage: "reference-note".to_string(),
                reason: "Identity branches should prefer clarifying companion references before spawning new structure, unless sovereignty explicitly requires a branch split.".to_string(),
                inventory_role,
                exists: true,
                line_count,
                densest_dimension_entries,
                has_subgroups,
                living_record_markers,
            };
        }
        return GrowthAssessment {
            stage: "flat".to_string(),
            reason: "The identity branch should remain compact until interpretation pressure justifies a governed reference note.".to_string(),
            inventory_role,
            exists: true,
            line_count,
            densest_dimension_entries,
            has_subgroups,
            living_record_markers,
        };
    }

    if has_subgroups && (line_count > 220 || densest_dimension_entries >= 10) {
        return GrowthAssessment {
            stage: "reference-note".to_string(),
            reason: "The SoT already shows subgrouping and is getting heavy enough that extraction into a reference note is warranted.".to_string(),
            inventory_role,
            exists: true,
            line_count,
            densest_dimension_entries,
            has_subgroups,
            living_record_markers,
        };
    }

    if line_count > 320 || (densest_dimension_entries >= 12 && living_record_markers >= 4) {
        return GrowthAssessment {
            stage: "spawn".to_string(),
            reason: "The content is heavy enough and operational enough that it likely deserves its own SoT rather than remaining a section or ref.".to_string(),
            inventory_role,
            exists: true,
            line_count,
            densest_dimension_entries,
            has_subgroups,
            living_record_markers,
        };
    }

    if densest_dimension_entries >= 8 {
        return GrowthAssessment {
            stage: "fractal".to_string(),
            reason: "One dimension has become dense enough that grouping by sub-blocks would likely improve scanability.".to_string(),
            inventory_role,
            exists: true,
            line_count,
            densest_dimension_entries,
            has_subgroups,
            living_record_markers,
        };
    }

    GrowthAssessment {
        stage: "flat".to_string(),
        reason: "The current SoT remains readable enough to stay flat.".to_string(),
        inventory_role,
        exists: true,
        line_count,
        densest_dimension_entries,
        has_subgroups,
        living_record_markers,
    }
}

pub fn plan_growth_execution(
    root: &Path,
    stage: &str,
    assessed_target: &str,
    proposal_target: &str,
    subject_hint: &str,
) -> (Option<GrowthExecutionPlan>, Vec<ValidationFinding>) {
    let target_path = Path::new(assessed_target);
    let stem = sanitize_growth_stem(
        target_path
            .file_stem()
            .and_then(|item| item.to_str())
            .unwrap_or("target"),
    );
    let proposal_name = Path::new(proposal_target)
        .file_stem()
        .and_then(|item| item.to_str())
        .unwrap_or("proposal");
    let source_path = root.join(assessed_target);
    let source_text = fs::read_to_string(&source_path).unwrap_or_default();

    if matches!(stage, "reference-note" | "fractal" | "spawn") && source_text.is_empty() {
        return (
            None,
            vec![ValidationFinding::error(
                "GROWTH_SOURCE_MISSING",
                format!("Growth target `{assessed_target}` is missing or unreadable"),
            )],
        );
    }

    if stage == "fractal" {
        return (
            Some(GrowthExecutionPlan {
                target: assessed_target.to_string(),
                kind: "fractalized-source".to_string(),
                dimension: String::new(),
                entries: Vec::new(),
            }),
            Vec::new(),
        );
    }

    if stage == "reference-note" {
        let (dimension, entries) = extract_reference_entries(&source_text);
        let target =
            numbered_reference_target(root, assessed_target, subject_hint).unwrap_or_else(|| {
                let ref_stem = stem.strip_suffix("-SoT").unwrap_or(&stem);
                format!("knowledge/ARTIFACTS/refs/Ref.{ref_stem}.md")
            });
        return (
            Some(GrowthExecutionPlan {
                target,
                kind: "reference-note".to_string(),
                dimension,
                entries,
            }),
            Vec::new(),
        );
    }

    if stage == "spawn" && assessed_target.ends_with("-SoT.md") {
        let target =
            numbered_spawn_target(root, assessed_target, subject_hint).unwrap_or_else(|| {
                let child_stem = stem.strip_suffix("-SoT").unwrap_or(&stem);
                let child_name = format!("{child_stem}.Spawned-Child-SoT.md");
                target_path
                    .with_file_name(child_name)
                    .to_string_lossy()
                    .replace('\\', "/")
            });
        return (
            Some(GrowthExecutionPlan {
                target,
                kind: "spawned-sot".to_string(),
                dimension: String::new(),
                entries: Vec::new(),
            }),
            Vec::new(),
        );
    }

    (
        Some(GrowthExecutionPlan {
            target: format!("knowledge/ARTIFACTS/proposals/Applied.{proposal_name}.md"),
            kind: "applied-action".to_string(),
            dimension: String::new(),
            entries: Vec::new(),
        }),
        Vec::new(),
    )
}

pub fn plan_growth_source_update(
    root: &Path,
    stage: &str,
    assessed_target: &str,
    execution_target: &str,
    proposal_target: &str,
) -> (Option<GrowthSourceUpdatePlan>, Vec<ValidationFinding>) {
    if !matches!(stage, "reference-note" | "spawn") {
        return (None, Vec::new());
    }

    let source_path = root.join(assessed_target);
    let source_text = match fs::read_to_string(&source_path) {
        Ok(text) => text,
        Err(_) => {
            return (
                None,
                vec![ValidationFinding::error(
                    "GROWTH_SOURCE_MISSING",
                    format!("Growth target `{assessed_target}` is missing or unreadable"),
                )],
            )
        }
    };

    let created = today_utc();
    let execution_name = Path::new(execution_target)
        .file_stem()
        .and_then(|item| item.to_str())
        .unwrap_or("execution");
    let parent_name = Path::new(assessed_target)
        .file_stem()
        .and_then(|item| item.to_str())
        .unwrap_or("parent");
    let stage_label = if stage == "reference-note" {
        "reference note"
    } else {
        "spawned child SoT"
    };
    let link_line = if stage == "reference-note" {
        format!("- Reference Note: [[{execution_name}]]")
    } else {
        format!("- Spawned Child: [[{execution_name}]]")
    };
    let decision_line = format!(
        "- [{created}] Growth proposal `{proposal_target}` created a {stage_label} `[[{execution_name}]]`."
    );
    let next_action_line = format!(
        "- Route detailed branch material through `[[{execution_name}]]` before adding more weight to `{parent_name}`. ({created})\n  - Growth should redirect future detail toward the lighter-weight structural outcome. [AGENT:gpt-5]"
    );
    let status_line = format!(
        "- A governed growth step created `[[{execution_name}]]` as the next structural home. ({created})\n  - The parent remains canonical for its scope while redirecting deeper material through the new structure. [AGENT:gpt-5]"
    );

    if stage == "reference-note" {
        let (dimension, entries) = extract_reference_entries(&source_text);
        let pointer = format!(
            "- Detailed entries moved to `[[{execution_name}]]`. ({created})\n  - The parent keeps the summary while the deeper detail now lives in the reference note. [AGENT:gpt-5]"
        );
        return (
            Some(GrowthSourceUpdatePlan {
                link_line,
                status_line,
                next_action_line,
                decision_line,
                target_dimension: dimension,
                replacement_entries: entries,
                active_pointer_line: pointer,
            }),
            Vec::new(),
        );
    }

    let counts = dimension_entry_counts_by_id(&source_text);
    let densest = counts
        .keys()
        .max_by_key(|dimension| {
            (
                counts.get(*dimension).copied().unwrap_or_default(),
                dimension_preference(dimension),
            )
        })
        .cloned()
        .unwrap_or_default();
    let pointer = format!(
        "- Branch-specific detail now continues in `[[{execution_name}]]`. ({created})\n  - The parent retains the summary while the new child SoT carries the deeper branch structure. [AGENT:gpt-5]"
    );
    (
        Some(GrowthSourceUpdatePlan {
            link_line,
            status_line,
            next_action_line,
            decision_line,
            target_dimension: dimension_heading(&source_text, &densest),
            replacement_entries: Vec::new(),
            active_pointer_line: pointer,
        }),
        Vec::new(),
    )
}

pub fn apply_growth_source_update(
    source_text: &str,
    stage: &str,
    plan: &GrowthSourceUpdatePlan,
) -> GrowthSourceApplyPlan {
    let mut updated = append_line_to_section(source_text, "### Links", &plan.link_line);
    updated = append_line_to_section(&updated, "### Status", &plan.status_line);
    updated = append_line_to_section(&updated, "### Next Actions", &plan.next_action_line);
    updated = append_line_to_section(&updated, "### Decisions", &plan.decision_line);
    if stage == "reference-note" {
        updated = replace_entries_with_reference_pointer(
            &updated,
            &plan.target_dimension,
            &plan.replacement_entries,
            &plan.active_pointer_line,
        );
    }
    if stage == "spawn" {
        updated = insert_spawn_branch_pointer(
            &updated,
            &plan.target_dimension,
            &plan.active_pointer_line,
        );
    }
    GrowthSourceApplyPlan {
        updated_content: updated,
    }
}

pub fn render_growth_reference_note(
    execution_target: &str,
    assessed_target: &str,
    proposal_target: &str,
    created: &str,
    dimension: &str,
    entries: &[String],
) -> String {
    let entry_text = if entries.is_empty() {
        "(No extracted entries.)".to_string()
    } else {
        entries.join("\n\n")
    };
    let execution_name = Path::new(execution_target)
        .file_name()
        .and_then(|item| item.to_str())
        .unwrap_or(execution_target);
    let parent_name = Path::new(assessed_target)
        .file_stem()
        .and_then(|item| item.to_str())
        .unwrap_or("parent");
    format!(
        "---\n\
sot-type: reference\n\
created: {created}\n\
last-rewritten: {created}\n\
parent: \"[[{parent_name}#{dimension}]]\"\n\
domain: growth\n\
status: active\n\
tags: [\"growth\",\"reference\"]\n\
---\n\n\
# Reference Note for {}\n\n\
## This Reference Note Exists Because the Parent Artifact Has Exceeded a Flat Shape\n\
The governed growth proposal `{}` recommended extraction into a reference note.\n\n\
## This Reference Note Points Back to the Assessed Parent Artifact\n\
- parent artifact: `[[{}]]`\n\
- proposal: `{}`\n\
- extracted from: `{}`\n\
- created: `{}`\n\n\
## This Reference Note Preserves the Extracted Active Entries\n\
{}\n",
        execution_name,
        proposal_target,
        parent_name,
        proposal_target,
        dimension,
        created,
        entry_text
    )
}

pub fn render_spawned_sot(
    execution_target: &str,
    assessed_target: &str,
    proposal_target: &str,
    created: &str,
) -> String {
    let source_name = Path::new(assessed_target)
        .file_stem()
        .and_then(|item| item.to_str())
        .unwrap_or("source");
    let parent_link =
        spawned_parent_link(execution_target).unwrap_or_else(|| format!("[[{source_name}]]"));
    let child_name = Path::new(execution_target)
        .file_name()
        .and_then(|item| item.to_str())
        .unwrap_or(execution_target);
    let child_subject = Path::new(execution_target)
        .file_stem()
        .and_then(|item| item.to_str())
        .and_then(matrix_subject_for_name)
        .unwrap_or_else(|| child_name.trim_end_matches(".md").to_string());
    format!(
        "---\n\
sot-type: system\n\
created: {created}\n\
last-rewritten: {created}\n\
parent: \"{parent_link}\"\n\
domain: growth\n\
status: active\n\
tags: [\"growth\",\"spawned\",\"sot\"]\n\
---\n\n\
# {child_name} Source of Truth\n\n\
## 000.Index\n\n\
### Subject Declaration\n\n\
**Subject:** {child_name} was spawned from a governed growth proposal.\n\
**Type:** system\n\
**Created:** {created}\n\
**Parent:** {parent_link}\n\n\
### Links\n\n\
- Parent: {parent_link}\n\
- Source Branch: [[{source_name}]]\n\
- Source Target: `{assessed_target}`\n\
- Cornerstone: [[Cornerstone.Knosence-SoT]]\n\
- Proposal: `{proposal_target}`\n\n\
### Inbox\n\n\
No pending items.\n\n\
### Status\n\n\
Newly spawned from a governed growth proposal.\n\n\
### Open Questions\n\n\
- Which parts of `{assessed_target}` now belong here permanently, and which should remain only as pointers in the parent? ({created})\n\
  - The child should become dense in its own subject rather than duplicating the whole parent. [AGENT:gpt-5]\n\n\
### Next Actions\n\n\
- Deepen this SoT with branch-specific facts before considering any further abstraction. ({created})\n\
  - Ordinary SoTs should stay content-dense until the growth ladder justifies fractal, ref, or spawn. [HUMAN]\n\n\
### Decisions\n\n\
- [{created}] Spawned child SoT created from `{proposal_target}`.\n\n\
### Block Map — Single Source\n\n\
| ID | Question | Dimension | This SoT's Name |\n\
|----|----------|-----------|-----------------|\n\
| 000 | — | Index | Index |\n\
| 100 | Who | Circle | Identity |\n\
| 200 | What | Domain | Scope |\n\
| 300 | Where | Terrain | Placement |\n\
| 400 | When | Chronicle | Timeline |\n\
| 500 | How | Method | Operation |\n\
| 600 | Why/Not | Compass | Rationale |\n\
| 700 | — | Archive | Archive |\n\n\
---\n\n\
## 100.WHO.Identity\n\n### Active\n\n- {child_subject} now has its own governed branch beneath {parent_link}. ({created})\n  - This child exists because the parent subject accumulated enough branch-specific weight to justify its own home. [HUMAN]\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 200.WHAT.Scope\n\n### Active\n\n- This SoT carries the branch-specific detail that should no longer stay packed into `{assessed_target}`. ({created})\n  - The child is expected to become content-dense before any future abstraction is considered. [HUMAN]\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 300.WHERE.Placement\n\n### Active\n\n- Canonical knowledge for this branch lives here in the flat matrix root, while runtime exhaust stays in `knowledge/ARTIFACTS/`. ({created})\n  - Matrix position is determined by ID, context, and suffix rather than by folders. [AGENT:gpt-5]\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 400.WHEN.Timeline\n\n### Active\n\n- This branch was spawned through governed growth on {created}. ({created})\n  - The timeline entry records the moment the branch became independent. [AGENT:gpt-5]\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 500.HOW.Method\n\n### Active\n\n- This SoT should deepen through normal entries first, then fractal, then ref extraction, and only then further spawning if pressure returns. ({created})\n  - The lightest intervention rule still applies inside the new child. [HUMAN]\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 600.WHY.Compass\n\n### Active\n\n- This branch exists to keep the parent readable while preserving one canonical home for the denser subject it was carrying. ({created})\n  - Spawn is justified only when one subject has clearly become its own thing. [HUMAN]\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 700.Archive\n\n(No archived entries.)\n"
    )
}

pub fn render_applied_growth_action(
    stage: &str,
    assessed_target: &str,
    proposal_target: &str,
) -> String {
    format!(
        "# Applied Growth Action\n\n\
## This Artifact Records the Governed Structural Action Chosen from the Growth Proposal\n\
Proposal `{}` was applied against `{}`.\n\n\
Recommended stage: `{}`.\n\n\
## This Artifact Records the Immediate Controlled Outcome\n\
- action kind: `{}`\n\
- assessed target: `{}`\n\
- direct canonical mutation was deferred in favor of a governed structural action artifact\n",
        proposal_target,
        assessed_target,
        stage,
        if stage.is_empty() { "unknown" } else { stage },
        assessed_target
    )
}

pub fn render_applied_growth_proposal(
    proposal_text: &str,
    execution_target: &str,
    stage: &str,
) -> String {
    let mut updated = proposal_text.replacen("status: proposed", "status: applied", 1);
    if updated.contains("## This Proposal Records the Applied Outcome") {
        return updated;
    }
    if !updated.ends_with('\n') {
        updated.push('\n');
    }
    updated.push_str(&format!(
        "\n## This Proposal Records the Applied Outcome\n- stage applied: `{}`\n- execution target: `{}`\n- proposal status changed from `proposed` to `applied`\n",
        stage, execution_target
    ));
    updated
}

pub fn render_fractalized_growth_source(
    source_text: &str,
    proposal_target: &str,
    created: &str,
) -> String {
    if source_text.lines().any(is_subgroup_heading) {
        return source_text.to_string();
    }

    let counts = dimension_entry_counts_by_id(source_text);
    if counts.is_empty() {
        return source_text.to_string();
    }
    let mut densest = String::new();
    let mut best_count = 0usize;
    for (dimension, count) in &counts {
        if *count > best_count {
            best_count = *count;
            densest = dimension.clone();
        }
    }
    let subgroup_heading = format!(
        "## {:03}.{}-Subgroup",
        densest.parse::<usize>().unwrap_or_default() + 10,
        dimension_label(source_text, &densest)
    );
    let subgroup = format!(
        "{subgroup_heading}\n\n### Active\n\n- Grouping scaffold created from `{proposal_target}`. ({created})\n  - This subgroup marks the first structural split inside the densest dimension. [AGENT:gpt-5]\n\n### Inactive\n\n(No inactive entries.)\n\n"
    );
    let anchor = next_top_level_heading_for_dimension(source_text, &densest);
    if anchor.is_empty() {
        format!("{}\n\n{}", source_text.trim_end(), subgroup)
    } else {
        source_text.replacen(&anchor, &format!("{subgroup}{anchor}"), 1)
    }
}

pub fn plan_archive_transaction(
    content: &str,
    dimension_heading: &str,
    entry_value: &str,
    archived_reason: &str,
    archived_date: &str,
    archive_stamp: &str,
) -> (Option<ArchiveTransactionPlan>, Vec<ValidationFinding>) {
    let Some((section_start, section_end, dimension_section)) =
        locate_dimension_section(content, dimension_heading)
    else {
        return (
            None,
            vec![ValidationFinding::error(
                "ARCHIVE_DIMENSION_NOT_FOUND",
                format!("Dimension not found: {dimension_heading}"),
            )],
        );
    };

    let Some((active_start, inactive_start)) = locate_active_inactive_bounds(&dimension_section)
    else {
        return (
            None,
            vec![ValidationFinding::error(
                "ARCHIVE_STRUCTURE_INVALID",
                format!("Dimension missing Active/Inactive sections: {dimension_heading}"),
            )],
        );
    };

    let active_section = &dimension_section[active_start..inactive_start];
    let Some(entry_block) = extract_entry_block(active_section, entry_value) else {
        return (
            None,
            vec![ValidationFinding::error(
                "ARCHIVE_ACTIVE_ENTRY_NOT_FOUND",
                format!("Active entry not found for archive: {entry_value}"),
            )],
        );
    };

    let archived_entry = format!(
        "{}\n  - Archived: {}\n  - Archived Reason: {}",
        entry_block, archived_date, archived_reason
    );
    let mut updated_active = active_section
        .replacen(&entry_block, "", 1)
        .trim_end()
        .to_string();
    if updated_active.trim() == "### Active" {
        updated_active = "### Active\n\n(No active entries.)".to_string();
    }

    let mut inactive_section = dimension_section[inactive_start..].to_string();
    let empty_inactive = "### Inactive\n\n(No inactive entries.)";
    if inactive_section.contains(empty_inactive) {
        inactive_section = inactive_section.replacen(
            empty_inactive,
            &format!("### Inactive\n\n{archived_entry}"),
            1,
        );
    } else if !inactive_section.contains(&archived_entry) {
        inactive_section = format!("{}\n\n{}\n", inactive_section.trim_end(), archived_entry);
    }

    let new_dimension_section = format!(
        "{}\n\n{}\n\n{}",
        dimension_heading,
        updated_active.trim_start_matches('\n'),
        inactive_section.trim_start_matches('\n')
    );
    let mut updated_content = format!(
        "{}{}{}",
        &content[..section_start],
        new_dimension_section,
        &content[section_end..]
    );

    let archive_heading = "## 700.Archive";
    let Some(archive_pos) = updated_content.find(archive_heading) else {
        return (
            None,
            vec![ValidationFinding::error(
                "ARCHIVE_BLOCK_MISSING",
                "700.Archive is missing from target SoT",
            )],
        );
    };
    let archive_entry = format!(
        "[{}] FROM: {}\n{}\n",
        archive_stamp, dimension_heading, archived_entry
    );
    if updated_content[archive_pos..].contains("(No archived entries.)") {
        updated_content =
            updated_content.replacen("(No archived entries.)", archive_entry.trim(), 1);
    } else {
        updated_content = format!("{}\n\n{}", updated_content.trim_end(), archive_entry);
    }

    (
        Some(ArchiveTransactionPlan {
            updated_content,
            archived_entry,
            archive_entry,
        }),
        Vec::new(),
    )
}

pub fn plan_cross_reference_update(
    content: &str,
    claimant_dimension_heading: &str,
    description: &str,
    primary_target_stem: &str,
    primary_dimension_heading: &str,
    date: &str,
) -> (Option<CrossReferencePlan>, Vec<ValidationFinding>) {
    let Some((section_start, section_end, section)) =
        locate_dimension_section(content, claimant_dimension_heading)
    else {
        return (
            None,
            vec![ValidationFinding::error(
                "CROSS_REFERENCE_DIMENSION_MISSING",
                format!("Claimant dimension not found: {claimant_dimension_heading}"),
            )],
        );
    };
    let Some((active_start, _inactive_start)) = locate_active_inactive_bounds(&section) else {
        return (
            None,
            vec![ValidationFinding::error(
                "CROSS_REFERENCE_ACTIVE_SECTION_MISSING",
                format!("Claimant Active section not found: {claimant_dimension_heading}"),
            )],
        );
    };
    let active = subsection(&section, "### Active");
    if active.is_empty() {
        return (
            None,
            vec![ValidationFinding::error(
                "CROSS_REFERENCE_ACTIVE_SECTION_MISSING",
                format!("Claimant Active section not found: {claimant_dimension_heading}"),
            )],
        );
    }
    let normalized_primary_dimension_heading = primary_dimension_heading
        .trim()
        .trim_start_matches('#')
        .trim();
    let pointer = format!(
        "- {}. See: [[{}#{}]] ({})",
        description, primary_target_stem, normalized_primary_dimension_heading, date
    );
    let updated_active = if active.contains(&pointer) {
        active.clone()
    } else if active.contains("(No active entries.)") {
        active.replacen("(No active entries.)", &pointer, 1)
    } else {
        format!("{}\n\n{}\n", active.trim_end(), pointer)
    };
    let updated_section = format!(
        "{}{}{}",
        &section[..active_start],
        updated_active,
        &section[active_start + active.len()..]
    );
    let updated_content = format!(
        "{}{}{}",
        &content[..section_start],
        updated_section,
        &content[section_end..]
    );
    (
        Some(CrossReferencePlan {
            pointer,
            updated_content,
        }),
        Vec::new(),
    )
}

pub fn parse_operations_state(state_json: &str) -> (OperationsState, Vec<ValidationFinding>) {
    let mut findings = Vec::new();
    let mut state = default_operations_state();
    let trimmed = state_json.trim();
    if trimmed.is_empty() || trimmed == "{}" {
        return (state, findings);
    }

    state.patrol = extract_operation_state_entry(trimmed, "patrol", &mut findings);
    state.night_cycle = extract_operation_state_entry(trimmed, "night-cycle", &mut findings);
    (state, findings)
}

pub fn update_operations_state(
    state_json: &str,
    name: &str,
    status: &str,
    requested_by: &str,
    started_at: Option<&str>,
    completed_at: Option<&str>,
    last_report_target: Option<&str>,
    last_error: Option<&str>,
    increment_runs: bool,
) -> (OperationsState, Vec<ValidationFinding>) {
    let (mut state, mut findings) = parse_operations_state(state_json);
    let Some(entry) = operation_state_entry_mut(&mut state, name) else {
        findings.push(ValidationFinding::error(
            "OPERATIONS_STATE_NAME_INVALID",
            format!("Unsupported operations state entry: {name}"),
        ));
        return (state, findings);
    };
    findings.extend(validate_operation_request(name, requested_by));
    findings.extend(validate_operation_state_transition(&entry.status, status));
    entry.status = status.to_string();
    entry.requested_by = requested_by.to_string();
    if let Some(value) = started_at {
        entry.last_started = value.to_string();
    }
    if let Some(value) = completed_at {
        entry.last_completed = value.to_string();
    }
    if let Some(value) = last_report_target {
        entry.last_report_target = value.to_string();
    }
    if let Some(value) = last_error {
        entry.last_error = value.to_string();
    }
    if increment_runs {
        entry.run_count += 1;
    }
    (state, findings)
}

pub fn render_operations_state_json(state: &OperationsState) -> String {
    format!(
        "{{\n  \"patrol\": {},\n  \"night-cycle\": {}\n}}",
        render_operation_state_entry_json(&state.patrol),
        render_operation_state_entry_json(&state.night_cycle)
    )
}

pub fn render_operation_lock_json(record: &OperationLockRecord) -> String {
    format!(
        "{{\n  \"name\": \"{}\",\n  \"requested_by\": \"{}\",\n  \"started_at\": \"{}\"\n}}",
        escape_json(&record.name),
        escape_json(&record.requested_by),
        escape_json(&record.started_at)
    )
}

pub fn plan_operation_start(
    current_state_json: &str,
    name: &str,
    requested_by: &str,
    started_at: &str,
) -> (Option<OperationLifecyclePlan>, Vec<ValidationFinding>) {
    let (state, findings) = update_operations_state(
        current_state_json,
        name,
        "running",
        requested_by,
        Some(started_at),
        None,
        None,
        None,
        false,
    );
    if !findings.is_empty() {
        return (None, findings);
    }
    let lock_record = OperationLockRecord {
        name: name.to_string(),
        requested_by: requested_by.to_string(),
        started_at: started_at.to_string(),
    };
    (
        Some(OperationLifecyclePlan {
            state_json: render_operations_state_json(&state),
            state_status: "running".to_string(),
            lock_target: format!("runtime/queues/operation-{name}.lock"),
            lock_content: render_operation_lock_json(&lock_record),
            release_lock: false,
        }),
        Vec::new(),
    )
}

pub fn plan_operation_state_update(
    current_state_json: &str,
    name: &str,
    status: &str,
    requested_by: &str,
    started_at: Option<&str>,
    completed_at: Option<&str>,
    last_report_target: Option<&str>,
    last_error: Option<&str>,
    increment_runs: bool,
    release_lock: bool,
) -> (Option<OperationLifecyclePlan>, Vec<ValidationFinding>) {
    let (state, findings) = update_operations_state(
        current_state_json,
        name,
        status,
        requested_by,
        started_at,
        completed_at,
        last_report_target,
        last_error,
        increment_runs,
    );
    if !findings.is_empty() {
        return (None, findings);
    }
    (
        Some(OperationLifecyclePlan {
            state_json: render_operations_state_json(&state),
            state_status: status.to_string(),
            lock_target: format!("runtime/queues/operation-{name}.lock"),
            lock_content: String::new(),
            release_lock,
        }),
        Vec::new(),
    )
}

pub fn plan_scheduler_run(
    current_state_json: &str,
    name: &str,
    requested_by: &str,
    interval_seconds: i64,
    max_runs: i32,
) -> (Option<SchedulerPlan>, Vec<ValidationFinding>) {
    let (_, mut findings) = parse_operations_state(current_state_json);
    findings.extend(validate_operation_request(name, requested_by));
    if interval_seconds < 0 || (interval_seconds == 0 && max_runs != 1) {
        findings.push(ValidationFinding::error(
            "SCHEDULER_INTERVAL_INVALID",
            format!("Scheduler interval must be positive for `{name}`."),
        ));
    }
    let (state, _) = parse_operations_state(current_state_json);
    let current_status = match name {
        "patrol" => state.patrol.status,
        "night-cycle" => state.night_cycle.status,
        _ => String::new(),
    };
    if !findings.is_empty() {
        return (None, findings);
    }
    (
        Some(SchedulerPlan {
            operation: name.to_string(),
            requested_by: requested_by.to_string(),
            interval_seconds: interval_seconds as u64,
            max_runs,
            unbounded: max_runs <= 0,
            current_status,
        }),
        Vec::new(),
    )
}

pub fn plan_operation_audit_event(
    kind: &str,
    event_id: &str,
    timestamp: &str,
    target: &str,
    reason: &str,
    artifacts_json: &str,
    validation_summary_json: &str,
    approval_required: bool,
) -> (
    Option<crate::models::EventAppendPlan>,
    Vec<ValidationFinding>,
) {
    let (endpoint, actor, status) = match kind {
        "patrol-blocked" => ("patrol", "warden", "blocked"),
        "patrol-completed" => ("patrol", "warden", "committed"),
        "night-cycle-blocked" => ("night-cycle", "dc", "blocked"),
        "night-cycle-completed" => ("night-cycle", "dc", "committed"),
        _ => {
            return (
                None,
                vec![ValidationFinding::error(
                    "OPERATION_EVENT_KIND_INVALID",
                    format!("Unsupported operation audit event kind: {kind}"),
                )],
            )
        }
    };
    let mut record = EventRecord::new(
        event_id, timestamp, "vela", endpoint, actor, target, status, reason,
    );
    record.approval_required = approval_required;
    if !validation_summary_json.trim().is_empty() {
        record.validation_summary = ValidationSummary {
            finding_codes: extract_json_string_list(validation_summary_json),
            blocking: validation_summary_json.contains("\"blocking\":true"),
        };
    }
    plan_event_append(&record, artifacts_json, validation_summary_json)
}

pub fn plan_dreamer_proposals(
    stamp: &str,
    blocked_items_json: &str,
) -> Vec<DreamerProposalCandidate> {
    let mut counts: BTreeMap<String, usize> = BTreeMap::new();
    for block in extract_object_blocks(blocked_items_json) {
        if let Some(reason) = extract_json_string(&block, "reason") {
            if !reason.trim().is_empty() {
                *counts.entry(reason).or_insert(0) += 1;
            }
        }
    }
    counts
        .into_iter()
        .filter(|(_, count)| *count >= 3)
        .map(|(reason, count)| DreamerProposalCandidate {
            target: format!(
                "knowledge/ARTIFACTS/proposals/Dreamer-Proposal.{stamp}.{}.md",
                slugify(&reason)
            ),
            reason,
            count,
        })
        .collect()
}

pub fn validate_operation_lock(
    lock_json: &str,
    expected_name: &str,
) -> (Option<OperationLockRecord>, Vec<ValidationFinding>) {
    let trimmed = lock_json.trim();
    if trimmed.is_empty() {
        return (
            None,
            vec![ValidationFinding::error(
                "OPERATION_LOCK_INVALID",
                format!("Operation lock for `{expected_name}` is empty"),
            )],
        );
    }

    let record = OperationLockRecord {
        name: extract_json_string(trimmed, "name").unwrap_or_default(),
        requested_by: extract_json_string(trimmed, "requested_by").unwrap_or_default(),
        started_at: extract_json_string(trimmed, "started_at").unwrap_or_default(),
    };

    let mut findings = Vec::new();
    if record.name.is_empty() || record.requested_by.is_empty() || record.started_at.is_empty() {
        findings.push(ValidationFinding::error(
            "OPERATION_LOCK_INVALID",
            format!("Operation lock for `{expected_name}` is missing required fields"),
        ));
    } else if record.name != expected_name {
        findings.push(ValidationFinding::error(
            "OPERATION_LOCK_INVALID",
            format!(
                "Operation lock for `{expected_name}` contains mismatched operation `{}`",
                record.name
            ),
        ));
    }

    (
        if findings.is_empty() {
            Some(record)
        } else {
            None
        },
        findings,
    )
}

pub fn validate_operation_request(name: &str, requested_by: &str) -> Vec<ValidationFinding> {
    if !matches!(name, "patrol" | "night-cycle") {
        return vec![ValidationFinding::error(
            "OPERATIONS_STATE_NAME_INVALID",
            format!("Unsupported operation: {name}"),
        )];
    }

    let allowed = match name {
        "patrol" => {
            matches!(requested_by, "human" | "system" | "n8n")
                || requested_by
                    .strip_prefix("night-cycle:")
                    .map(|item| matches!(item, "human" | "system" | "n8n"))
                    .unwrap_or(false)
        }
        "night-cycle" => matches!(requested_by, "human" | "system" | "n8n"),
        _ => false,
    };

    if allowed {
        Vec::new()
    } else {
        vec![ValidationFinding::error(
            "OPERATION_REQUEST_NOT_ALLOWED",
            format!("Requester `{requested_by}` may not start operation `{name}`"),
        )]
    }
}

pub fn validate_operation_state_transition(
    current_status: &str,
    next_status: &str,
) -> Vec<ValidationFinding> {
    let current = if current_status.trim().is_empty() {
        "idle"
    } else {
        current_status
    };
    let allowed = match (current, next_status) {
        ("idle", "running" | "blocked") => true,
        ("running", "completed" | "blocked") => true,
        ("completed", "running" | "blocked") => true,
        ("blocked", "running" | "blocked") => true,
        _ => false,
    };

    if allowed {
        Vec::new()
    } else {
        vec![ValidationFinding::error(
            "OPERATION_STATE_TRANSITION_INVALID",
            format!("Operation state may not transition from `{current}` to `{next_status}`"),
        )]
    }
}

pub fn validate_dreamer_review(current_status: &str, decision: &str) -> Vec<ValidationFinding> {
    let mut findings = Vec::new();
    if !matches!(decision, "approved" | "denied" | "needs-more-info") {
        findings.push(ValidationFinding::error(
            "DREAMER_REVIEW_DECISION_INVALID",
            format!("Unsupported decision: {decision}"),
        ));
    }
    if !matches!(current_status, "proposed" | "unknown" | "") {
        findings.push(ValidationFinding::error(
            "DREAMER_PROPOSAL_STATUS_INVALID",
            format!("Dreamer proposal may not be reviewed from status `{current_status}`"),
        ));
    }
    findings
}

pub fn validate_dreamer_follow_up_apply(
    current_status: &str,
    actor: &str,
) -> Vec<ValidationFinding> {
    let mut findings = Vec::new();
    if !matches!(actor, "human" | "system") {
        findings.push(ValidationFinding::error(
            "DREAMER_FOLLOW_UP_ACTOR_NOT_ALLOWED",
            format!("Actor `{actor}` may not apply Dreamer follow ups."),
        ));
    }
    if !matches!(current_status, "proposed" | "applied") {
        findings.push(ValidationFinding::error(
            "DREAMER_FOLLOW_UP_STATUS_INVALID",
            format!("Dreamer follow up is not executable from status `{current_status}`."),
        ));
    }
    findings
}

pub fn classify_dreamer_follow_up(reason: &str) -> String {
    let lowered = reason.to_lowercase();
    if [
        "validator",
        "validation",
        "rule",
        "frontmatter",
        "structure",
    ]
    .iter()
    .any(|token| lowered.contains(token))
    {
        "validator-change".to_string()
    } else if ["workflow", "triage", "route", "pipeline", "queue"]
        .iter()
        .any(|token| lowered.contains(token))
    {
        "workflow-change".to_string()
    } else {
        "refusal-tightening".to_string()
    }
}

pub fn list_merge_candidates(root: &str) -> Vec<MergeCandidateSummary> {
    let knowledge_root = Path::new(root).join("knowledge");
    let Ok(entries) = fs::read_dir(&knowledge_root) else {
        return Vec::new();
    };
    let mut owners_by_ref: BTreeMap<String, std::collections::BTreeSet<String>> = BTreeMap::new();
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let Some(name) = path.file_name().and_then(|item| item.to_str()) else {
            continue;
        };
        if !name.ends_with("-SoT.md") {
            continue;
        }
        let rel = path
            .strip_prefix(root)
            .ok()
            .map(|item| item.to_string_lossy().replace('\\', "/"))
            .unwrap_or_else(|| path.to_string_lossy().replace('\\', "/"));
        let Ok(text) = fs::read_to_string(&path) else {
            continue;
        };
        for target in extract_reference_targets(&text) {
            owners_by_ref.entry(target).or_default().insert(rel.clone());
        }
    }
    owners_by_ref
        .into_iter()
        .filter_map(|(ref_target, owners)| {
            let count = owners.len();
            if count >= 3 {
                Some(MergeCandidateSummary {
                    ref_target,
                    owners: owners.into_iter().collect(),
                    count,
                })
            } else {
                None
            }
        })
        .collect()
}

pub fn validate_dreamer_follow_up_kind(kind: &str) -> Vec<ValidationFinding> {
    if matches!(
        kind,
        "validator-change" | "workflow-change" | "refusal-tightening"
    ) {
        Vec::new()
    } else {
        vec![ValidationFinding::error(
            "DREAMER_FOLLOW_UP_KIND_INVALID",
            format!("Unsupported Dreamer follow up kind: {kind}"),
        )]
    }
}

pub fn dreamer_follow_up_registry_mode(kind: &str) -> Result<&'static str, Vec<ValidationFinding>> {
    let findings = validate_dreamer_follow_up_kind(kind);
    if !findings.is_empty() {
        return Err(findings);
    }
    Ok(match kind {
        "validator-change" => "validator",
        "workflow-change" => "workflow",
        "refusal-tightening" => "refusal",
        _ => unreachable!(),
    })
}

pub fn dreamer_follow_up_queue_name(kind: &str) -> Result<&'static str, Vec<ValidationFinding>> {
    let findings = validate_dreamer_follow_up_kind(kind);
    if !findings.is_empty() {
        return Err(findings);
    }
    Ok(match kind {
        "validator-change" => "Validator-Change-Queue",
        "workflow-change" => "Workflow-Change-Queue",
        "refusal-tightening" => "Refusal-Tightening-Queue",
        _ => unreachable!(),
    })
}

pub fn validate_dreamer_execution_artifact(content: &str) -> Vec<ValidationFinding> {
    let required = [
        "# Dreamer Execution",
        "## This Reference Records the Concrete Queue Item Opened from an Approved Dreamer Follow Up",
        "## Classification",
        "- kind:",
        "- pattern:",
        "- queue:",
        "## Execution",
        "- reason:",
        "- next step:",
    ];
    missing_shape_findings(content, &required, "DREAMER_EXECUTION_SHAPE_INVALID")
}

pub fn validate_warden_patrol_report(content: &str) -> Vec<ValidationFinding> {
    let required = [
        "# Warden Patrol Report",
        "## This Report Records the Latest Patrol Validation Pass Over Recent Day Shift Activity",
        "## Checked Targets",
        "## Structural Flags",
        "## Cosmetic Fixes",
    ];
    missing_shape_findings(content, &required, "WARDEN_PATROL_REPORT_INVALID")
}

pub fn validate_dc_night_report(content: &str) -> Vec<ValidationFinding> {
    let required = [
        "# DC Night Report",
        "## This Report Records the Coordinated Night Cycle Across Patrol, Growth Review, and Pattern Review",
        "## Warden Patrol Summary",
        "## Grower Activity",
        "## Dreamer Activity",
        "## Dreamer Proposals",
        "## Blocked (Needs Dario)",
    ];
    missing_shape_findings(content, &required, "DC_NIGHT_REPORT_INVALID")
}

pub fn validate_dreamer_pattern_report(content: &str) -> Vec<ValidationFinding> {
    let required = [
        "# Dreamer Pattern Report",
        "## This Report Records Repeated Blocked Patterns Worth Further Review",
        "## Three Strike Patterns",
        "## Proposed Responses",
        "## Recent Blocked Items",
    ];
    missing_shape_findings(content, &required, "DREAMER_PATTERN_REPORT_INVALID")
}

pub fn render_warden_patrol_report(
    stamp: &str,
    requested_by: &str,
    checked_targets: &[String],
    structural_flag_targets: &[String],
) -> String {
    let checked_lines = if checked_targets.is_empty() {
        "- No patched targets were available.".to_string()
    } else {
        checked_targets
            .iter()
            .map(|target| format!("- `{target}`"))
            .collect::<Vec<String>>()
            .join("\n")
    };
    let flag_lines = if structural_flag_targets.is_empty() {
        "- No structural flags.".to_string()
    } else {
        structural_flag_targets
            .iter()
            .map(|target| format!("- `{target}`"))
            .collect::<Vec<String>>()
            .join("\n")
    };
    format!(
        "# Warden Patrol Report\n\n\
## This Report Records the Latest Patrol Validation Pass Over Recent Day Shift Activity\n\
Patrol `{stamp}` was requested by `{requested_by}` and validated the latest patched targets.\n\n\
## Checked Targets\n\n\
{checked_lines}\n\n\
## Structural Flags\n\n\
{flag_lines}\n\n\
## Cosmetic Fixes\n\n\
- No cosmetic fixes were applied in this skeleton patrol.\n"
    )
}

pub fn render_dc_night_report(
    stamp: &str,
    requested_by: &str,
    patrol_report_target: &str,
    files_checked: usize,
    structural_flags_count: usize,
    growth_candidates_json: &str,
    dreamer_patterns_json: &str,
    blocked_items_json: &str,
    dreamer_report_target: &str,
    dreamer_proposals_json: &str,
) -> String {
    let growth_lines = render_growth_candidates(growth_candidates_json);
    let pattern_lines = render_pattern_counts(dreamer_patterns_json);
    let blocked_lines = render_blocked_items(blocked_items_json);
    let proposal_lines = render_dreamer_proposals(dreamer_proposals_json, true);
    format!(
        "# DC Night Report\n\n\
## This Report Records the Coordinated Night Cycle Across Patrol, Growth Review, and Pattern Review\n\
Night cycle `{stamp}` was requested by `{requested_by}` and packaged the current operational state.\n\n\
## Warden Patrol Summary\n\n\
- Patrol report: `[[{}]]`\n\
- Files checked: {files_checked}\n\
- Structural flags: {structural_flags_count}\n\n\
## Grower Activity\n\n\
{growth_lines}\n\n\
## Dreamer Activity\n\n\
- Pattern report: `[[{}]]`\n\
{pattern_lines}\n\n\
## Dreamer Proposals\n\n\
{proposal_lines}\n\n\
## Blocked (Needs Dario)\n\n\
{blocked_lines}\n",
        stem_or_empty(patrol_report_target),
        stem_or_empty(dreamer_report_target),
    )
}

pub fn render_dreamer_pattern_report(
    stamp: &str,
    requested_by: &str,
    dreamer_patterns_json: &str,
    blocked_items_json: &str,
    dreamer_proposals_json: &str,
) -> String {
    let strike_lines = render_three_strike_patterns(dreamer_patterns_json);
    let recent_lines = render_recent_blocked_items(blocked_items_json);
    let proposal_lines = render_dreamer_proposals(dreamer_proposals_json, false);
    format!(
        "# Dreamer Pattern Report\n\n\
## This Report Records Repeated Blocked Patterns Worth Further Review\n\
Dreamer review `{stamp}` was requested by `{requested_by}` and scanned recent blocked events.\n\n\
## Three Strike Patterns\n\n\
{strike_lines}\n\n\
## Proposed Responses\n\n\
{proposal_lines}\n\n\
## Recent Blocked Items\n\n\
{recent_lines}\n"
    )
}

pub fn render_dreamer_proposal(
    created: &str,
    stamp: &str,
    requested_by: &str,
    reason: &str,
    count: usize,
    blocked_items_json: &str,
) -> String {
    let evidence_lines = render_matching_blocked_item_evidence(blocked_items_json, reason);
    format!(
        "---\n\
sot-type: proposal\n\
created: {created}\n\
last-rewritten: {created}\n\
parent: \"[[100.WHO.Circle-SoT]]\"\n\
domain: operations\n\
status: proposed\n\
tags: [\"dreamer\",\"proposal\",\"night-cycle\"]\n\
---\n\n\
# Dreamer Proposal\n\n\
## This Proposal Records a Repeated Night Cycle Failure Pattern That Merits Follow Up\n\
Dreamer opened this proposal during `{stamp}` for `{requested_by}` after observing `{count}` repeated blocks.\n\n\
## Pattern\n\n\
- reason: `{reason}`\n\
- strikes: `{count}`\n\n\
## Evidence\n\n\
{evidence_lines}\n\n\
## Proposed Response\n\n\
- Review the validator or workflow path that is producing `{reason}`.\n\
- Decide whether the correct next step is a rule change, a workflow change, or a stricter refusal.\n"
    )
}

pub fn render_dreamer_follow_up(
    created: &str,
    proposal_target: &str,
    reason: &str,
    classification: &str,
    actor: &str,
) -> String {
    format!(
        "---\n\
sot-type: proposal\n\
created: {created}\n\
last-rewritten: {created}\n\
parent: \"[[{}]]\"\n\
domain: operations\n\
status: proposed\n\
tags: [\"dreamer\",\"follow-up\",\"proposal\"]\n\
---\n\n\
# Dreamer Follow Up\n\n\
## This Proposal Records the Concrete Follow Up Opened After an Approved Dreamer Review\n\
Approved Dreamer proposal `[[{}]]` opened this `{classification}` follow up.\n\n\
## Classification\n\n\
- kind: `{classification}`\n\
- reason: `{reason}`\n\
- reviewed by: `{actor}`\n\n\
## Suggested Next Step\n\n\
- Apply a targeted {classification} change and verify it against the repeated failure signal.\n",
        stem_or_empty(proposal_target),
        stem_or_empty(proposal_target),
    )
}

pub fn render_dreamer_execution_artifact(
    created: &str,
    follow_up_target: &str,
    actor: &str,
    kind: &str,
    follow_up_reason: &str,
    queue_name: &str,
    execution_reason: &str,
) -> String {
    format!(
        "---\n\
sot-type: reference\n\
created: {created}\n\
last-rewritten: {created}\n\
parent: \"[[{}]]\"\n\
domain: operations\n\
status: active\n\
tags: [\"dreamer\",\"execution\",\"operations\"]\n\
---\n\n\
# Dreamer Execution\n\n\
## This Reference Records the Concrete Queue Item Opened from an Approved Dreamer Follow Up\n\
Follow up `[[{}]]` was executed by `{actor}` and opened a concrete `{kind}` queue item.\n\n\
## Classification\n\n\
- kind: `{kind}`\n\
- pattern: `{follow_up_reason}`\n\
- queue: `[[{queue_name}]]`\n\n\
## Execution\n\n\
- reason: {execution_reason}\n\
- next step: implement the queued change through the governed validation or workflow path.\n",
        stem_or_empty(follow_up_target),
        stem_or_empty(follow_up_target),
    )
}

pub fn dreamer_proposal_reason(text: &str) -> String {
    extract_markdown_field(text, "- reason:")
}

pub fn dreamer_follow_up_kind(text: &str) -> String {
    extract_markdown_field(text, "- kind:")
}

pub fn dreamer_follow_up_reason(text: &str) -> String {
    extract_markdown_field(text, "- reason:")
}

pub fn dreamer_existing_execution_target(text: &str) -> Option<String> {
    for line in text.lines() {
        if line.starts_with("- execution:") {
            return line
                .split("[[")
                .nth(1)
                .and_then(|item| item.split("]]").next())
                .map(|item| item.to_string());
        }
    }
    None
}

pub fn render_reviewed_dreamer_proposal(
    text: &str,
    decision: &str,
    actor: &str,
    reason: &str,
    follow_up_target: Option<&str>,
) -> String {
    let updated = replace_frontmatter_status(text, decision);
    let mut review_section = format!(
        "\n## Review Outcome\n\n- decision: `{decision}`\n- actor: `{actor}`\n- reason: {reason}\n"
    );
    if let Some(target) = follow_up_target {
        review_section.push_str(&format!("- follow up: `[[{}]]`\n", stem_or_empty(target)));
    }
    replace_or_append_section(&updated, "## Review Outcome", &review_section)
}

pub fn render_applied_dreamer_follow_up(
    text: &str,
    actor: &str,
    reason: &str,
    execution_target: &str,
) -> String {
    let updated = replace_frontmatter_status(text, "applied");
    let execution_section = format!(
        "\n## Execution Outcome\n\n- decision: `applied`\n- actor: `{actor}`\n- reason: {reason}\n- execution: `[[{}]]`\n",
        stem_or_empty(execution_target),
    );
    replace_or_append_section(&updated, "## Execution Outcome", &execution_section)
}

pub fn list_dreamer_proposals(repo_root: &str) -> Vec<DreamerProposalSummary> {
    discover_dreamer_files(repo_root, "Dreamer-Proposal.")
        .into_iter()
        .map(|(target, text)| DreamerProposalSummary {
            target,
            status: extract_frontmatter_value(&text, "status")
                .unwrap_or_else(|| "unknown".to_string()),
            created: extract_frontmatter_value(&text, "created").unwrap_or_default(),
            reason: dreamer_proposal_reason(&text),
        })
        .collect()
}

pub fn list_dreamer_follow_ups(repo_root: &str) -> Vec<DreamerFollowUpSummary> {
    discover_dreamer_files(repo_root, "Dreamer-Follow-Up.")
        .into_iter()
        .map(|(target, text)| DreamerFollowUpSummary {
            target,
            status: extract_frontmatter_value(&text, "status")
                .unwrap_or_else(|| "unknown".to_string()),
            created: extract_frontmatter_value(&text, "created").unwrap_or_default(),
            kind: dreamer_follow_up_kind(&text),
            reason: dreamer_follow_up_reason(&text),
        })
        .collect()
}

pub fn list_merge_follow_ups(repo_root: &str) -> Vec<MergeFollowUpSummary> {
    discover_dreamer_files(repo_root, "Merge-Follow-Up.")
        .into_iter()
        .map(|(target, text)| MergeFollowUpSummary {
            target,
            status: extract_frontmatter_value(&text, "status")
                .unwrap_or_else(|| "unknown".to_string()),
            ref_target: extract_frontmatter_value(&text, "ref-target").unwrap_or_default(),
            suggested_target: extract_frontmatter_value(&text, "suggested-target").unwrap_or_default(),
        })
        .collect()
}

pub fn list_merge_proposals(repo_root: &str) -> Vec<MergeProposalSummary> {
    discover_dreamer_files(repo_root, "Merge-Proposal.")
        .into_iter()
        .map(|(target, text)| MergeProposalSummary {
            target,
            status: extract_frontmatter_value(&text, "status")
                .unwrap_or_else(|| "unknown".to_string()),
            ref_target: extract_frontmatter_value(&text, "ref-target").unwrap_or_default(),
            count: extract_frontmatter_value(&text, "entity-count")
                .and_then(|item| item.parse::<usize>().ok())
                .unwrap_or(0),
        })
        .collect()
}

pub fn render_reviewed_merge_proposal(
    text: &str,
    decision: &str,
    actor: &str,
    reason: &str,
    follow_up_target: Option<&str>,
) -> String {
    let updated = replace_frontmatter_status(text, decision);
    let mut review_section = format!(
        "\n## Review Outcome\n\n- decision: `{decision}`\n- actor: `{actor}`\n- reason: {reason}\n"
    );
    if let Some(target) = follow_up_target {
        review_section.push_str(&format!("- follow up: `[[{}]]`\n", stem_or_empty(target)));
    }
    replace_or_append_section(&updated, "## Review Outcome", &review_section)
}

pub fn render_merge_follow_up(
    created: &str,
    proposal_target: &str,
    ref_target: &str,
    count: usize,
    actor: &str,
    reason: &str,
    suggested_target: &str,
) -> String {
    format!(
        "---\n\
sot-type: proposal\n\
created: {created}\n\
last-rewritten: {created}\n\
parent: \"[[{}]]\"\n\
domain: governance\n\
status: proposed\n\
ref-target: \"{ref_target}\"\n\
entity-count: \"{count}\"\n\
suggested-target: \"{suggested_target}\"\n\
tags: [\"merge\",\"follow-up\",\"matrix\",\"governance\"]\n\
---\n\n\
# Merge Follow Up\n\n\
## This Follow Up Reserves The Governed Consolidation Step\n\
The repeated ref `[[{}]]` has been approved for merge review and now needs a canonical SoT home.\n\n\
## This Follow Up Records The Suggested Canonical Target\n\n\
- suggested target: `[[{}]]`\n\
- source proposal: `[[{}]]`\n\
- repeated entity count: `{count}`\n\n\
## This Follow Up Records The Review Context\n\n\
- reviewer: `{actor}`\n\
- reason: {reason}\n\n\
## This Follow Up Leaves Apply Work For Governed Execution\n\n\
- next step: create the canonical SoT at the suggested target, then repoint the prior entities to that SoT through governed mutation.\n",
        stem_or_empty(proposal_target),
        stem_or_empty(ref_target),
        stem_or_empty(suggested_target),
        stem_or_empty(proposal_target),
    )
}

pub fn render_applied_merge_follow_up(
    text: &str,
    execution_target: &str,
    owners: &[String],
) -> String {
    let updated = replace_frontmatter_status(text, "applied");
    let owner_lines = if owners.is_empty() {
        "- repointed owner: (none)".to_string()
    } else {
        owners
            .iter()
            .map(|owner| format!("- repointed owner: `[[{}]]`", stem_or_empty(owner)))
            .collect::<Vec<String>>()
            .join("\n")
    };
    let execution_section = format!(
        "\n## Execution Outcome\n\n- canonical target: `[[{}]]`\n{}\n",
        stem_or_empty(execution_target),
        owner_lines,
    );
    replace_or_append_section(&updated, "## Execution Outcome", &execution_section)
}

pub fn render_merge_spawned_sot(
    execution_target: &str,
    ref_target: &str,
    owners: &[String],
) -> String {
    let created = today_utc();
    let parent_link = spawned_parent_link(execution_target)
        .unwrap_or_else(|| "[[200.WHAT.Domain-SoT#200.WHAT.Domain]]".to_string());
    let child_name = Path::new(execution_target)
        .file_name()
        .and_then(|item| item.to_str())
        .unwrap_or(execution_target);
    let child_subject = Path::new(execution_target)
        .file_stem()
        .and_then(|item| item.to_str())
        .and_then(matrix_subject_for_name)
        .unwrap_or_else(|| child_name.trim_end_matches(".md").to_string());
    let owner_lines = if owners.is_empty() {
        "- Source owner: (no owners recorded)".to_string()
    } else {
        owners
            .iter()
            .map(|owner| format!("- Source owner: [[{}]]", stem_or_empty(owner)))
            .collect::<Vec<String>>()
            .join("\n")
    };
    format!(
        "---\n\
sot-type: system\n\
created: {created}\n\
last-rewritten: {created}\n\
parent: \"{parent_link}\"\n\
domain: merge\n\
status: active\n\
tags: [\"merge\",\"canonical\",\"sot\"]\n\
---\n\n\
# {child_subject} Source of Truth\n\n\
## 000.Index\n\n\
### Subject Declaration\n\n\
**Subject:** This SoT is the canonical home for `{child_subject}` after governed merge consolidation.\n\
**Type:** system\n\
**Created:** {created}\n\
**Parent:** {parent_link}\n\n\
### Links\n\n\
- Parent: {parent_link}\n\
- Cornerstone: [[Cornerstone.Knosence-SoT]]\n\
- Origin Ref: [[{}]]\n\
{owner_lines}\n\n\
### Inbox\n\n\
No pending items.\n\n\
### Status\n\n\
- `{child_subject}` has been merged into one canonical SoT. ({created})\n\
  - Repeated refs across multiple entities triggered governed consolidation. [HUMAN]\n\n\
### Open Questions\n\n\
- Which details from the prior owners should remain here as dense canonical content? ({created})\n\
  - The merged SoT should deepen directly rather than re-fragment into repeated refs. [HUMAN]\n\n\
### Next Actions\n\n\
- Consolidate the repeated subject here and keep the former owners as one-line pointers only. ({created})\n\
  - Merge before spawn wins once a subject repeats broadly enough. [HUMAN]\n\n\
### Decisions\n\n\
- [{created}] Canonical merge SoT created from repeated ref `[[{}]]`.\n\n\
### Block Map — Single Source\n\n\
| ID | Question | Dimension | This SoT's Name |\n\
|----|----------|-----------|-----------------|\n\
| 000 | — | Index | Index |\n\
| 100 | Who | Circle | Circle |\n\
| 200 | What | Domain | Domain |\n\
| 300 | Where | Terrain | Terrain |\n\
| 400 | When | Chronicle | Chronicle |\n\
| 500 | How | Method | Method |\n\
| 600 | Why/Not | Compass | Compass |\n\
| 700 | — | Archive | Archive |\n\n\
---\n\n\
## 100.WHO.Circle\n\n### Active\n\n\
- `{child_subject}` is now treated as one governed subject rather than a repeated ref. ({created})\n\
  - The merge establishes one canonical identity for the subject inside this matrix. [HUMAN]\n\n\
### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 200.WHAT.Domain\n\n### Active\n\n\
- This SoT is the canonical home for content previously referenced through `[[{}]]`. ({created})\n\
  - Prior entities should now point here instead of carrying the repeated ref. [HUMAN]\n\n\
### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 300.WHERE.Terrain\n\n### Active\n\n\
- Canonical merged knowledge lives in the flat matrix root with position determined by ID, context, and suffix. ({created})\n\
  - The matrix stays flat while the numbering carries structure. [HUMAN]\n\n\
### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 400.WHEN.Chronicle\n\n### Active\n\n\
- This subject became a canonical SoT through merge governance on {created}. ({created})\n\
  - The merge threshold was triggered by repeated references across multiple entities. [AGENT:gpt-5]\n\n\
### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 500.HOW.Method\n\n### Active\n\n\
- Future updates should be merged here directly unless the growth ladder later justifies fractal, ref, or spawn. ({created})\n\
  - Merge happens before new proliferation. [HUMAN]\n\n\
### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 600.WHY.Compass\n\n### Active\n\n\
- This SoT exists to prevent fragmentation and restore one canonical place to look. ({created})\n\
  - The matrix stays coherent when repeated subjects consolidate. [HUMAN]\n\n\
### Inactive\n\n(No inactive entries.)\n\n---\n\n\
## 700.Archive\n\n(No archived entries.)\n",
        stem_or_empty(ref_target),
        stem_or_empty(ref_target),
        stem_or_empty(ref_target),
    )
}

pub fn merge_follow_up_ref_target(text: &str) -> String {
    extract_frontmatter_value(text, "ref-target").unwrap_or_default()
}

pub fn merge_follow_up_suggested_target(text: &str) -> String {
    extract_frontmatter_value(text, "suggested-target").unwrap_or_default()
}

pub fn suggest_merge_target(root: &Path, ref_target: &str) -> Option<String> {
    let mut name = Path::new(ref_target).file_name()?.to_str()?.to_string();
    if !name.ends_with(".md") {
        name.push_str(".md");
    }
    let mut parts = name.splitn(3, '.');
    let numeric_id = parts.next()?;
    let _context = parts.next()?;
    let rest = parts.next()?;
    if numeric_id.len() != 4 && numeric_id.len() != 3 {
        // allow refs like 240a...
    }
    let hub_id = hub_id_for_numeric_id(&numeric_id[..3].to_string())?;
    let next_id = next_available_direct_child_id(root, &hub_id)?;
    let context = hub_context_for_numeric_id(&hub_id)?;
    let subject = rest.strip_suffix("-Ref.md")?;
    Some(format!("knowledge/{next_id}.{context}.{subject}-SoT.md"))
}

pub fn plan_merge_review(
    root: &Path,
    target: &str,
    current_text: &str,
    decision: &str,
    actor: &str,
    reason: &str,
    created: &str,
) -> (Option<MergeReviewPlan>, Vec<ValidationFinding>) {
    let current_status =
        extract_frontmatter_value(current_text, "status").unwrap_or_else(|| "unknown".to_string());
    if current_status != "proposed" {
        return (
            None,
            vec![ValidationFinding::error(
                "MERGE_PROPOSAL_STATE_INVALID",
                format!("Merge proposal `{target}` is not in proposed state"),
            )],
        );
    }
    if !matches!(decision, "approved" | "denied" | "needs-more-info") {
        return (
            None,
            vec![ValidationFinding::error(
                "MERGE_REVIEW_DECISION_INVALID",
                format!("Unsupported merge review decision: {decision}"),
            )],
        );
    }
    let proposal_update = render_reviewed_merge_proposal(current_text, decision, actor, reason, None);
    if decision != "approved" {
        return (
            Some(MergeReviewPlan {
                target: target.to_string(),
                decision: decision.to_string(),
                follow_up_target: String::new(),
                suggested_target: String::new(),
                updated_content: proposal_update,
                follow_up_content: String::new(),
            }),
            Vec::new(),
        );
    }
    let ref_target = extract_frontmatter_value(current_text, "ref-target").unwrap_or_default();
    let count = extract_frontmatter_value(current_text, "entity-count")
        .and_then(|item| item.parse::<usize>().ok())
        .unwrap_or(0);
    let follow_up_target = target.replace("Merge-Proposal.", "Merge-Follow-Up.");
    let suggested_target = suggest_merge_target(root, &ref_target).unwrap_or_default();
    let follow_up_content = render_merge_follow_up(
        created,
        target,
        &ref_target,
        count,
        actor,
        reason,
        &suggested_target,
    );
    let updated_content = render_reviewed_merge_proposal(
        current_text,
        decision,
        actor,
        reason,
        Some(&follow_up_target),
    );
    (
        Some(MergeReviewPlan {
            target: target.to_string(),
            decision: decision.to_string(),
            follow_up_target,
            suggested_target,
            updated_content,
            follow_up_content,
        }),
        Vec::new(),
    )
}

pub fn plan_merge_follow_up_apply(
    root: &Path,
    target: &str,
    current_text: &str,
    actor: &str,
) -> (Option<MergeApplyPlan>, Vec<ValidationFinding>) {
    let current_status =
        extract_frontmatter_value(current_text, "status").unwrap_or_else(|| "unknown".to_string());
    if !matches!(actor, "human" | "system") {
        return (
            None,
            vec![ValidationFinding::error(
                "MERGE_FOLLOW_UP_ACTOR_NOT_ALLOWED",
                format!("Actor `{actor}` cannot apply merge follow ups"),
            )],
        );
    }
    if current_status == "applied" {
        let execution_target = merge_follow_up_suggested_target(current_text);
        return (
            Some(MergeApplyPlan {
                target: target.to_string(),
                execution_target: execution_target.clone(),
                ref_target: merge_follow_up_ref_target(current_text),
                owners: Vec::new(),
                owner_updates: Vec::new(),
                execution_content: String::new(),
                updated_follow_up_content: current_text.to_string(),
                already_applied: true,
            }),
            Vec::new(),
        );
    }
    if current_status != "proposed" {
        return (
            None,
            vec![ValidationFinding::error(
                "MERGE_FOLLOW_UP_STATE_INVALID",
                format!("Merge follow up `{target}` is not in proposed state"),
            )],
        );
    }
    let ref_target = merge_follow_up_ref_target(current_text);
    let mut execution_target = merge_follow_up_suggested_target(current_text);
    if execution_target.is_empty() {
        execution_target = suggest_merge_target(root, &ref_target).unwrap_or_default();
    }
    let owners = list_merge_candidates(root.to_string_lossy().as_ref())
        .into_iter()
        .find(|item| item.ref_target == ref_target)
        .map(|item| item.owners)
        .unwrap_or_default();
    let owner_updates = owners
        .iter()
        .filter_map(|owner| {
            let owner_path = root.join(owner);
            let text = fs::read_to_string(&owner_path).ok()?;
            Some(MergeOwnerUpdate {
                target: owner.clone(),
                updated_content: replace_ref_with_sot_pointer(&text, &ref_target, &execution_target),
            })
        })
        .collect::<Vec<MergeOwnerUpdate>>();
    let execution_content = render_merge_spawned_sot(&execution_target, &ref_target, &owners);
    let updated_follow_up_content = render_applied_merge_follow_up(current_text, &execution_target, &owners);
    (
        Some(MergeApplyPlan {
            target: target.to_string(),
            execution_target,
            ref_target,
            owners,
            owner_updates,
            execution_content,
            updated_follow_up_content,
            already_applied: false,
        }),
        Vec::new(),
    )
}

pub fn plan_dreamer_review(
    target: &str,
    current_text: &str,
    decision: &str,
    actor: &str,
    reason: &str,
    created: &str,
) -> (Option<DreamerReviewPlan>, Vec<ValidationFinding>) {
    let current_status =
        extract_frontmatter_value(current_text, "status").unwrap_or_else(|| "unknown".to_string());
    let findings = validate_dreamer_review(&current_status, decision);
    if !findings.is_empty() {
        return (None, findings);
    }
    let proposal_update =
        render_reviewed_dreamer_proposal(current_text, decision, actor, reason, None);
    if decision != "approved" {
        return (
            Some(DreamerReviewPlan {
                target: target.to_string(),
                decision: decision.to_string(),
                follow_up_target: String::new(),
                follow_up_kind: String::new(),
                updated_content: proposal_update,
                follow_up_content: String::new(),
            }),
            Vec::new(),
        );
    }
    let follow_up_reason = dreamer_proposal_reason(current_text);
    let follow_up_kind = classify_dreamer_follow_up(&follow_up_reason);
    let follow_up_target = target.replace("Dreamer-Proposal.", "Dreamer-Follow-Up.");
    let follow_up_content =
        render_dreamer_follow_up(created, target, &follow_up_reason, &follow_up_kind, actor);
    let updated_content = render_reviewed_dreamer_proposal(
        current_text,
        decision,
        actor,
        reason,
        Some(&follow_up_target),
    );
    (
        Some(DreamerReviewPlan {
            target: target.to_string(),
            decision: decision.to_string(),
            follow_up_target,
            follow_up_kind,
            updated_content,
            follow_up_content,
        }),
        Vec::new(),
    )
}

pub fn plan_dreamer_follow_up_apply(
    target: &str,
    current_text: &str,
    actor: &str,
    reason: &str,
    created: &str,
) -> (Option<DreamerApplyPlan>, Vec<ValidationFinding>) {
    let current_status =
        extract_frontmatter_value(current_text, "status").unwrap_or_else(|| "unknown".to_string());
    let findings = validate_dreamer_follow_up_apply(&current_status, actor);
    if !findings.is_empty() {
        return (None, findings);
    }
    let kind = dreamer_follow_up_kind(current_text);
    if current_status == "applied" {
        return (
            Some(DreamerApplyPlan {
                target: target.to_string(),
                kind,
                execution_target: dreamer_existing_execution_target(current_text)
                    .unwrap_or_default(),
                execution_content: String::new(),
                updated_follow_up_content: current_text.to_string(),
                already_applied: true,
            }),
            Vec::new(),
        );
    }
    let execution_target = target.replace(
        "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.",
        "knowledge/ARTIFACTS/refs/Dreamer-Execution.",
    );
    let queue_name = dreamer_follow_up_queue_name(&kind).unwrap_or("Dreamer-Action-Queue");
    let follow_up_reason = dreamer_follow_up_reason(current_text);
    let execution_content = render_dreamer_execution_artifact(
        created,
        target,
        actor,
        &kind,
        &follow_up_reason,
        queue_name,
        reason,
    );
    let updated_follow_up_content =
        render_applied_dreamer_follow_up(current_text, actor, reason, &execution_target);
    (
        Some(DreamerApplyPlan {
            target: target.to_string(),
            kind,
            execution_target,
            execution_content,
            updated_follow_up_content,
            already_applied: false,
        }),
        Vec::new(),
    )
}

pub fn plan_warden_patrol(
    stamp: &str,
    requested_by: &str,
    checked_targets_json: &str,
    structural_flag_targets_json: &str,
) -> (Option<PatrolPlan>, Vec<ValidationFinding>) {
    let checked_targets = extract_json_string_list(checked_targets_json);
    let structural_flag_targets = extract_json_string_list(structural_flag_targets_json);
    let report_target = format!("knowledge/ARTIFACTS/refs/Warden-Patrol-{stamp}.md");
    let report_content = render_warden_patrol_report(
        stamp,
        requested_by,
        &checked_targets,
        &structural_flag_targets,
    );
    let findings = validate_warden_patrol_report(&report_content);
    if !findings.is_empty() {
        return (None, findings);
    }
    (
        Some(PatrolPlan {
            report_target,
            report_content,
            files_checked: checked_targets.len(),
            structural_flags_count: structural_flag_targets.len(),
        }),
        Vec::new(),
    )
}

pub fn plan_night_cycle(
    stamp: &str,
    requested_by: &str,
    patrol_report_target: &str,
    files_checked: usize,
    structural_flags_count: usize,
    growth_candidates_json: &str,
    dreamer_patterns_json: &str,
    blocked_items_json: &str,
    dreamer_proposals_json: &str,
) -> (Option<NightCyclePlan>, Vec<ValidationFinding>) {
    let dreamer_report_target =
        format!("knowledge/ARTIFACTS/refs/Dreamer-Pattern-Report-{stamp}.md");
    let dreamer_report_content = render_dreamer_pattern_report(
        stamp,
        requested_by,
        dreamer_patterns_json,
        blocked_items_json,
        dreamer_proposals_json,
    );
    let dreamer_findings = validate_dreamer_pattern_report(&dreamer_report_content);
    if !dreamer_findings.is_empty() {
        return (None, dreamer_findings);
    }

    let report_target = format!("knowledge/ARTIFACTS/refs/DC-Night-Report-{stamp}.md");
    let report_content = render_dc_night_report(
        stamp,
        requested_by,
        patrol_report_target,
        files_checked,
        structural_flags_count,
        growth_candidates_json,
        dreamer_patterns_json,
        blocked_items_json,
        &dreamer_report_target,
        dreamer_proposals_json,
    );
    let report_findings = validate_dc_night_report(&report_content);
    if !report_findings.is_empty() {
        return (None, report_findings);
    }
    (
        Some(NightCyclePlan {
            report_target,
            report_content,
            dreamer_report_target,
            dreamer_report_content,
            growth_candidates_count: extract_object_blocks(growth_candidates_json).len(),
            blocked_items_count: extract_object_blocks(blocked_items_json).len(),
        }),
        Vec::new(),
    )
}

pub fn parse_dreamer_action_registry(
    registry_json: &str,
) -> (DreamerActionRegistry, Vec<ValidationFinding>) {
    let validator_changes = extract_bucket_entries(registry_json, "validator_changes");
    let workflow_changes = extract_bucket_entries(registry_json, "workflow_changes");
    let refusal_tightenings = extract_bucket_entries(registry_json, "refusal_tightenings");
    let registry = DreamerActionRegistry {
        validator_changes,
        workflow_changes,
        refusal_tightenings,
    };

    let mut findings = Vec::new();
    for (bucket, actions) in [
        ("validator_changes", &registry.validator_changes),
        ("workflow_changes", &registry.workflow_changes),
        ("refusal_tightenings", &registry.refusal_tightenings),
    ] {
        for action in actions {
            if action.pattern_reason.trim().is_empty() {
                findings.push(ValidationFinding::error(
                    "DREAMER_ACTION_PATTERN_REQUIRED",
                    format!("Dreamer action in `{bucket}` is missing pattern_reason"),
                ));
            }
            if action.status.trim().is_empty() {
                findings.push(ValidationFinding::error(
                    "DREAMER_ACTION_STATUS_REQUIRED",
                    format!("Dreamer action in `{bucket}` is missing status"),
                ));
            }
        }
    }

    (registry, findings)
}

pub fn register_dreamer_action(
    registry_json: &str,
    kind: &str,
    action: DreamerAction,
) -> (DreamerActionRegistry, Vec<ValidationFinding>) {
    let (mut registry, mut findings) = parse_dreamer_action_registry(registry_json);
    let bucket = bucket_entries_mut(&mut registry, kind);
    if bucket.is_empty() && !matches!(kind, "validator" | "workflow" | "refusal") {
        findings.push(ValidationFinding::error(
            "DREAMER_ACTION_KIND_INVALID",
            format!("Unsupported Dreamer action kind: {kind}"),
        ));
        return (registry, findings);
    }
    if !bucket
        .iter()
        .any(|item| item.follow_up_target == action.follow_up_target)
    {
        bucket.push(action);
    }
    (registry, findings)
}

pub fn update_dreamer_action_status(
    registry_json: &str,
    follow_up_target: &str,
    status: &str,
) -> (DreamerActionRegistry, Vec<ValidationFinding>) {
    let (mut registry, mut findings) = parse_dreamer_action_registry(registry_json);
    let mut updated = false;
    for bucket in [
        &mut registry.validator_changes,
        &mut registry.workflow_changes,
        &mut registry.refusal_tightenings,
    ] {
        for action in bucket.iter_mut() {
            if action.follow_up_target == follow_up_target {
                action.status = status.to_string();
                updated = true;
            }
        }
    }
    if !updated {
        findings.push(ValidationFinding::error(
            "DREAMER_ACTION_NOT_FOUND",
            format!("Dreamer action not found for follow up target: {follow_up_target}"),
        ));
    }
    (registry, findings)
}

pub fn route_inbox_entry(text: &str) -> Option<&'static str> {
    let lowered = text.to_lowercase();
    let rules: [(&str, &[&str]); 6] = [
        (
            "100",
            &[
                "joined",
                "manages",
                "role",
                "team",
                "person",
                "owner",
                "assistant",
                "profile",
                "human",
            ],
        ),
        (
            "200",
            &[
                "definition",
                "scope",
                "deliverable",
                "component",
                "framework",
                "what is",
                "capabilities",
            ],
        ),
        (
            "300",
            &[
                "platform",
                "tool",
                "environment",
                "repository",
                "repo",
                "account",
                "deployed",
                "nixos",
                "obsidian",
            ],
        ),
        (
            "400",
            &[
                "deadline",
                "milestone",
                "quarterly",
                "cadence",
                "timeline",
                "started",
                "schedule",
                "date",
            ],
        ),
        (
            "500",
            &[
                "process",
                "procedure",
                "protocol",
                "method",
                "workflow",
                "convention",
                "how",
                "result types",
            ],
        ),
        (
            "600",
            &[
                "because",
                "reason",
                "rationale",
                "trade-off",
                "tradeoff",
                "why",
                "chose",
                "risk",
            ],
        ),
    ];

    for (dimension, markers) in rules {
        if markers.iter().any(|marker| lowered.contains(marker)) {
            return Some(dimension);
        }
    }
    None
}

pub fn plan_inbox_entry(
    root: &Path,
    text: &str,
    source_name: &str,
) -> (Option<InboxTriagePlan>, Vec<ValidationFinding>) {
    let Some(dimension) = route_inbox_entry(text) else {
        return (
            None,
            vec![ValidationFinding::error(
                "INBOX_DIMENSION_UNRESOLVED",
                "Dimension router could not classify inbox item",
            )],
        );
    };
    let Some(target) = extract_target(root, text) else {
        return (
            None,
            vec![ValidationFinding::error(
                "INBOX_TARGET_MISSING",
                format!("Inbox item `{source_name}` is missing a target SoT declaration"),
            )],
        );
    };
    let (value, context) = extract_entry(text, source_name);
    (
        Some(InboxTriagePlan {
            target,
            dimension: dimension.to_string(),
            value,
            context,
        }),
        Vec::new(),
    )
}

pub fn plan_csv_inbox(
    root: &Path,
    text: &str,
    source_name: &str,
) -> (Option<CsvInboxPlan>, Vec<ValidationFinding>) {
    let Some(target) = extract_target(root, text) else {
        return (
            None,
            vec![ValidationFinding::error(
                "INBOX_TARGET_MISSING",
                format!("Inbox item `{source_name}` is missing a target SoT declaration"),
            )],
        );
    };
    let rows = parse_csv_rows(text);
    if rows.is_empty() {
        return (
            None,
            vec![ValidationFinding::error(
                "INBOX_CSV_EMPTY",
                "CSV inbox item had no extractable rows",
            )],
        );
    }
    let mut entries = Vec::new();
    for row in rows {
        let (value, context) = entry_from_csv_row(&row);
        let route_text = format!("{value} {context}");
        let dimension = row
            .get("dimension")
            .map(|item| item.trim().to_string())
            .filter(|item| !item.is_empty())
            .or_else(|| route_inbox_entry(&route_text).map(|item| item.to_string()));
        let Some(dimension) = dimension else {
            return (
                None,
                vec![ValidationFinding::error(
                    "INBOX_CSV_DIMENSION_UNRESOLVED",
                    "CSV inbox row could not be classified",
                )],
            );
        };
        entries.push(CsvInboxEntry {
            dimension,
            value,
            context,
        });
    }
    (Some(CsvInboxPlan { target, entries }), Vec::new())
}

pub fn plan_companion_path(
    root: &Path,
    source_rel: &str,
    target_rel: &str,
    date_stamp: &str,
) -> (Option<CompanionPathPlan>, Vec<ValidationFinding>) {
    let source_path = root.join(source_rel);
    let target_path = root.join(target_rel);
    let Some(extension) = source_path.extension().and_then(|item| item.to_str()) else {
        return (
            None,
            vec![ValidationFinding::error(
                "INBOX_COMPANION_EXTENSION_MISSING",
                format!("Inbox source `{source_rel}` has no extension"),
            )],
        );
    };
    let target_stem = target_path
        .file_stem()
        .and_then(|item| item.to_str())
        .unwrap_or("target");
    let parent = target_path.parent().unwrap_or(root);
    let preferred = parent.join(format!("{target_stem}.{extension}"));
    let destination = if preferred.exists() {
        parent.join(format!("{target_stem}-{date_stamp}.{extension}"))
    } else {
        preferred
    };
    let destination = destination
        .strip_prefix(root)
        .ok()
        .map(|path| path.to_string_lossy().replace('\\', "/"))
        .unwrap_or_else(|| destination.to_string_lossy().replace('\\', "/"));
    (Some(CompanionPathPlan { destination }), Vec::new())
}

fn extract_target(root: &Path, text: &str) -> Option<String> {
    let trimmed = text.trim_start();
    if let Some(rest) = trimmed.strip_prefix("---\n") {
        if let Some(end_idx) = rest.find("\n---\n") {
            let frontmatter = &rest[..end_idx];
            for line in frontmatter.lines() {
                let candidate = line.trim();
                if let Some(value) = candidate.strip_prefix("target:") {
                    if let Some(target) = normalize_target(root, value.trim()) {
                        return Some(target);
                    }
                }
            }
        }
    }
    for line in text.lines() {
        let mut candidate = line.trim();
        if candidate.starts_with('#') {
            candidate = candidate.trim_start_matches('#').trim();
        }
        if candidate.to_ascii_lowercase().starts_with("target:") {
            let value = candidate
                .split_once(':')
                .map(|(_, right)| right.trim())
                .unwrap_or("");
            if let Some(target) = normalize_target(root, value) {
                return Some(target);
            }
        }
    }
    None
}

fn normalize_target(root: &Path, raw_value: &str) -> Option<String> {
    let mut value = raw_value
        .trim()
        .trim_matches('`')
        .trim_matches('"')
        .trim_matches('\'')
        .to_string();
    if value.starts_with("[[") && value.ends_with("]]") && value.len() > 4 {
        value = value[2..value.len() - 2].to_string();
    }
    if let Some((before_hash, _)) = value.split_once('#') {
        value = before_hash.trim().to_string();
    }
    if value.is_empty() {
        return None;
    }
    if let Some(resolved) = resolve_existing_target(root, &value) {
        return Some(resolved);
    }
    if value.to_ascii_lowercase().ends_with(".md") {
        if value.starts_with("knowledge/") {
            return Some(value);
        }
        return Some(format!("knowledge/{value}"));
    }
    Some(format!("knowledge/{value}.md"))
}

fn resolve_existing_target(root: &Path, value: &str) -> Option<String> {
    let normalized = if value.to_ascii_lowercase().ends_with(".md") {
        value.to_string()
    } else {
        format!("{value}.md")
    };
    let direct = root.join(&normalized);
    if direct.is_file() {
        return direct
            .strip_prefix(root)
            .ok()
            .map(|path| path.to_string_lossy().replace('\\', "/"));
    }
    let mut matches = Vec::new();
    collect_named_files(root, &normalized, &mut matches);
    if matches.len() == 1 {
        return matches.pop().and_then(|path| {
            path.strip_prefix(root)
                .ok()
                .map(|item| item.to_string_lossy().replace('\\', "/"))
        });
    }
    None
}

fn collect_named_files(root: &Path, name: &str, matches: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let file_name = entry.file_name();
        let file_name = file_name.to_string_lossy();
        if file_name == ".git" {
            continue;
        }
        if path.is_dir() {
            collect_named_files(&path, name, matches);
        } else if file_name == name {
            matches.push(path);
        }
    }
}

fn extract_entry(text: &str, source_name: &str) -> (String, String) {
    let body = strip_frontmatter(text);
    let mut lines = Vec::new();
    for line in body.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        if trimmed.to_ascii_lowercase().starts_with("target:") {
            continue;
        }
        lines.push(trimmed.to_string());
    }
    if lines
        .first()
        .map(|line| line.starts_with('#'))
        .unwrap_or(false)
    {
        lines.remove(0);
    }
    let mut value = lines
        .first()
        .map(|line| line.trim_start_matches('-').trim().to_string())
        .unwrap_or_else(|| fallback_source_title(source_name));
    if !ends_with_iso_date(&value) {
        value = format!("{value}. ({})", current_date());
    }
    let context_lines: Vec<String> = lines
        .into_iter()
        .skip(1)
        .filter(|line| !line.starts_with('#'))
        .collect();
    let context = if context_lines.is_empty() {
        "Extracted from Inbox during governed triage.".to_string()
    } else {
        context_lines.join(" ")
    };
    (value, context)
}

fn strip_frontmatter(text: &str) -> &str {
    if let Some(rest) = text.strip_prefix("---\n") {
        if let Some(idx) = rest.find("\n---\n") {
            return &rest[idx + 5..];
        }
    }
    text
}

fn fallback_source_title(source_name: &str) -> String {
    let stem = Path::new(source_name)
        .file_stem()
        .and_then(|item| item.to_str())
        .unwrap_or("inbox-item");
    stem.replace('-', " ")
}

fn ends_with_iso_date(value: &str) -> bool {
    if let Some(stripped) = value.strip_suffix(')') {
        if let Some((_, date_part)) = stripped.rsplit_once('(') {
            let date = date_part.trim();
            return is_iso_date(date);
        }
    }
    false
}

fn is_iso_date(value: &str) -> bool {
    let bytes = value.as_bytes();
    if bytes.len() != 10 {
        return false;
    }
    bytes[4] == b'-'
        && bytes[7] == b'-'
        && bytes.iter().enumerate().all(|(idx, byte)| {
            if idx == 4 || idx == 7 {
                true
            } else {
                byte.is_ascii_digit()
            }
        })
}

fn current_date() -> &'static str {
    "2026-04-10"
}

fn parse_csv_rows(text: &str) -> Vec<BTreeMap<String, String>> {
    let mut data_lines = Vec::new();
    for line in text.lines() {
        if !line.trim_start().starts_with('#') && !line.trim().is_empty() {
            data_lines.push(line);
        }
    }
    if data_lines.is_empty() {
        return Vec::new();
    }
    let headers: Vec<String> = data_lines[0]
        .split(',')
        .map(|item| item.trim().to_ascii_lowercase())
        .collect();
    let mut rows = Vec::new();
    for line in data_lines.into_iter().skip(1) {
        let values: Vec<String> = line
            .split(',')
            .map(|item| item.trim().to_string())
            .collect();
        let mut row = BTreeMap::new();
        for (idx, header) in headers.iter().enumerate() {
            row.insert(header.clone(), values.get(idx).cloned().unwrap_or_default());
        }
        if row.values().any(|item| !item.is_empty()) {
            rows.push(row);
        }
    }
    rows
}

fn entry_from_csv_row(row: &BTreeMap<String, String>) -> (String, String) {
    let mut value = row
        .get("value")
        .or_else(|| row.get("title"))
        .or_else(|| row.get("subject"))
        .cloned()
        .unwrap_or_default();
    let context = row
        .get("context")
        .or_else(|| row.get("detail"))
        .or_else(|| row.get("notes"))
        .cloned()
        .filter(|item| !item.is_empty())
        .unwrap_or_else(|| "Extracted from Inbox CSV during governed triage.".to_string());
    if value.is_empty() {
        value = "Inbox CSV entry".to_string();
    }
    if !ends_with_iso_date(&value) {
        value = format!("{value}. ({})", current_date());
    }
    (value, context)
}

pub fn subject_declaration_changed(before: &str, after: &str) -> bool {
    subject_declaration_block(before) != subject_declaration_block(after)
}

pub fn validate_subject_declaration_change(
    before: &str,
    after: &str,
    approval_granted: bool,
) -> Vec<ValidationFinding> {
    if !approval_granted && subject_declaration_changed(before, after) {
        return vec![ValidationFinding::error(
            "SUBJECT_DECLARATION_APPROVAL_REQUIRED",
            "Subject Declaration changes require explicit human approval",
        )];
    }
    Vec::new()
}

pub fn validate_growth_stage(stage: &str, approval_granted: bool) -> Vec<ValidationFinding> {
    if stage == "spawn" && !approval_granted {
        return vec![ValidationFinding::error(
            "SPAWN_APPROVAL_REQUIRED",
            "Spawn proposals require explicit human approval before a new SoT can be created",
        )];
    }
    Vec::new()
}

pub fn validate_archive_postconditions(
    content: &str,
    entry_value: &str,
    archived_reason: &str,
    dimension_heading: &str,
) -> Vec<ValidationFinding> {
    match archive_postcondition_failure(content, entry_value, archived_reason, dimension_heading) {
        Some(detail) => vec![ValidationFinding::error(
            "ARCHIVE_POSTCONDITION_FAILED",
            detail,
        )],
        None => Vec::new(),
    }
}

pub fn match_dreamer_actions(
    registry_json: &str,
    mode: &str,
    target: &str,
    endpoint: &str,
    reason: &str,
    content: &str,
) -> Vec<DreamerActionMatch> {
    let (registry, _) = parse_dreamer_action_registry(registry_json);
    let haystack = format!("{target} {endpoint} {reason} {content}").to_lowercase();
    bucket_entries(&registry, mode)
        .into_iter()
        .filter(|item| item.status == "active")
        .filter(|item| {
            let tokens = meaningful_tokens(&item.pattern_reason);
            !tokens.is_empty() && tokens.iter().any(|token| haystack.contains(token))
        })
        .map(|item| DreamerActionMatch {
            pattern_reason: item.pattern_reason.clone(),
            status: item.status.clone(),
        })
        .collect()
}

fn bucket_entries<'a>(registry: &'a DreamerActionRegistry, mode: &str) -> &'a [DreamerAction] {
    match mode {
        "validator" => &registry.validator_changes,
        "workflow" => &registry.workflow_changes,
        "refusal" => &registry.refusal_tightenings,
        _ => &[],
    }
}

fn stem_or_empty(path: &str) -> String {
    path.rsplit('/')
        .next()
        .unwrap_or(path)
        .trim_end_matches(".md")
        .to_string()
}

fn render_growth_candidates(growth_candidates_json: &str) -> String {
    let entries = extract_object_blocks(growth_candidates_json);
    if entries.is_empty() {
        return "- No active growth candidates.".to_string();
    }
    entries
        .iter()
        .map(|entry| {
            let target = extract_json_string(entry, "target").unwrap_or_default();
            let stage = extract_json_string(entry, "stage").unwrap_or_default();
            let inventory_role = extract_json_string(entry, "inventory_role").unwrap_or_default();
            format!("- `{target}` -> `{stage}` ({inventory_role})")
        })
        .collect::<Vec<String>>()
        .join("\n")
}

fn render_pattern_counts(patterns_json: &str) -> String {
    let entries = extract_json_map_entries(patterns_json);
    if entries.is_empty() {
        return "- No blocked-pattern signals recorded.".to_string();
    }
    entries
        .iter()
        .map(|(reason, count)| format!("- `{reason}` -> {count}"))
        .collect::<Vec<String>>()
        .join("\n")
}

fn render_three_strike_patterns(patterns_json: &str) -> String {
    let lines = extract_json_map_entries(patterns_json)
        .into_iter()
        .filter(|(_, count)| *count >= 3)
        .map(|(reason, count)| format!("- `{reason}` -> {count} strikes"))
        .collect::<Vec<String>>();
    if lines.is_empty() {
        "- No 3-strike patterns detected.".to_string()
    } else {
        lines.join("\n")
    }
}

fn render_blocked_items(blocked_items_json: &str) -> String {
    let entries = extract_object_blocks(blocked_items_json);
    if entries.is_empty() {
        return "- Spawn recommendations and constitutional rule changes remain human-gated."
            .to_string();
    }
    entries
        .iter()
        .take(5)
        .map(|entry| {
            let target = extract_json_string(entry, "target").unwrap_or_default();
            let endpoint = extract_json_string(entry, "endpoint").unwrap_or_default();
            let actor = extract_json_string(entry, "actor").unwrap_or_default();
            let reason = extract_json_string(entry, "reason").unwrap_or_default();
            format!(
                "- `{target}`\n  Attempted: `{endpoint}` by `{actor}`\n  Blocked because: {reason}"
            )
        })
        .collect::<Vec<String>>()
        .join("\n")
}

fn render_recent_blocked_items(blocked_items_json: &str) -> String {
    let entries = extract_object_blocks(blocked_items_json);
    if entries.is_empty() {
        return "- No blocked items recorded.".to_string();
    }
    entries
        .iter()
        .take(5)
        .map(|entry| {
            let target = extract_json_string(entry, "target").unwrap_or_default();
            let endpoint = extract_json_string(entry, "endpoint").unwrap_or_default();
            let reason = extract_json_string(entry, "reason").unwrap_or_default();
            format!("- `{reason}` on `{target}` via `{endpoint}`")
        })
        .collect::<Vec<String>>()
        .join("\n")
}

fn render_dreamer_proposals(dreamer_proposals_json: &str, include_strike_count: bool) -> String {
    let entries = extract_object_blocks(dreamer_proposals_json);
    if entries.is_empty() {
        return if include_strike_count {
            "- No Dreamer proposals opened this cycle.".to_string()
        } else {
            "- No Dreamer proposals were created.".to_string()
        };
    }
    entries
        .iter()
        .map(|entry| {
            let target = extract_json_string(entry, "target").unwrap_or_default();
            let reason = extract_json_string(entry, "reason").unwrap_or_default();
            if include_strike_count {
                let count = extract_json_number(entry, "count").unwrap_or(0);
                format!(
                    "- `[[{}]]` for `{reason}` ({count} strikes)",
                    stem_or_empty(&target)
                )
            } else {
                format!("- `[[{}]]` for `{reason}`", stem_or_empty(&target))
            }
        })
        .collect::<Vec<String>>()
        .join("\n")
}

fn render_matching_blocked_item_evidence(blocked_items_json: &str, reason: &str) -> String {
    let matches = extract_object_blocks(blocked_items_json)
        .into_iter()
        .filter(|entry| extract_json_string(entry, "reason").unwrap_or_default() == reason)
        .take(5)
        .map(|entry| {
            let target = extract_json_string(&entry, "target").unwrap_or_default();
            let endpoint = extract_json_string(&entry, "endpoint").unwrap_or_default();
            let actor = extract_json_string(&entry, "actor").unwrap_or_default();
            format!("- `{target}` via `{endpoint}` by `{actor}`")
        })
        .collect::<Vec<String>>();
    if matches.is_empty() {
        "- No matching blocked items remained available.".to_string()
    } else {
        matches.join("\n")
    }
}

fn extract_markdown_field(text: &str, prefix: &str) -> String {
    for line in text.lines() {
        if line.starts_with(prefix) {
            return line
                .split_once(':')
                .map(|(_, value)| value.trim().trim_matches('`').to_string())
                .unwrap_or_default();
        }
    }
    String::new()
}

fn extract_frontmatter_value(text: &str, key: &str) -> Option<String> {
    let mut lines = text.lines();
    if lines.next()? != "---" {
        return None;
    }
    for line in lines {
        if line == "---" {
            break;
        }
        if let Some((line_key, value)) = line.split_once(':') {
            if line_key.trim() == key {
                return Some(value.trim().trim_matches('"').to_string());
            }
        }
    }
    None
}

fn replace_frontmatter_status(text: &str, status: &str) -> String {
    text.lines()
        .map(|line| {
            if line.starts_with("status: ") {
                format!("status: {status}")
            } else {
                line.to_string()
            }
        })
        .collect::<Vec<String>>()
        .join("\n")
}

fn replace_or_append_section(text: &str, heading: &str, section: &str) -> String {
    if let Some(start) = text.find(&format!("\n{heading}")) {
        format!("{}{}", &text[..start], section)
    } else {
        format!("{}{}", text.trim_end(), section)
    }
}

fn discover_dreamer_files(repo_root: &str, prefix: &str) -> Vec<(String, String)> {
    let proposals_dir = Path::new(repo_root).join("knowledge/ARTIFACTS/proposals");
    let mut items: Vec<(String, String)> = Vec::new();
    if let Ok(entries) = fs::read_dir(&proposals_dir) {
        let mut paths: Vec<PathBuf> = entries
            .filter_map(|entry| entry.ok().map(|item| item.path()))
            .filter(|path| {
                path.file_name()
                    .and_then(|name| name.to_str())
                    .map(|name| name.starts_with(prefix) && name.ends_with(".md"))
                    .unwrap_or(false)
            })
            .collect();
        paths.sort();
        for path in paths {
            if let Ok(text) = fs::read_to_string(&path) {
                let relative = path
                    .strip_prefix(repo_root)
                    .ok()
                    .map(|item| item.to_string_lossy().to_string())
                    .unwrap_or_else(|| path.to_string_lossy().to_string());
                items.push((relative, text));
            }
        }
    }
    items
}

fn bucket_entries_mut<'a>(
    registry: &'a mut DreamerActionRegistry,
    mode: &str,
) -> &'a mut Vec<DreamerAction> {
    match mode {
        "validator" => &mut registry.validator_changes,
        "workflow" => &mut registry.workflow_changes,
        "refusal" => &mut registry.refusal_tightenings,
        _ => &mut registry.workflow_changes,
    }
}

fn operation_state_entry_mut<'a>(
    state: &'a mut OperationsState,
    name: &str,
) -> Option<&'a mut OperationStateEntry> {
    match name {
        "patrol" => Some(&mut state.patrol),
        "night-cycle" => Some(&mut state.night_cycle),
        _ => None,
    }
}

fn default_operation_state_entry() -> OperationStateEntry {
    OperationStateEntry {
        status: "idle".to_string(),
        last_started: String::new(),
        last_completed: String::new(),
        last_report_target: String::new(),
        last_error: String::new(),
        requested_by: String::new(),
        run_count: 0,
    }
}

fn render_operation_state_entry_json(entry: &OperationStateEntry) -> String {
    format!(
        "{{\"status\":\"{}\",\"last_started\":\"{}\",\"last_completed\":\"{}\",\"last_report_target\":\"{}\",\"last_error\":\"{}\",\"requested_by\":\"{}\",\"run_count\":{}}}",
        escape_json(&entry.status),
        escape_json(&entry.last_started),
        escape_json(&entry.last_completed),
        escape_json(&entry.last_report_target),
        escape_json(&entry.last_error),
        escape_json(&entry.requested_by),
        entry.run_count,
    )
}

pub fn plan_dimension_append(
    content: &str,
    dimension: &str,
    value: &str,
    context: &str,
) -> (Option<DimensionAppendPlan>, Vec<ValidationFinding>) {
    let heading = dimension_heading(content, dimension);
    if heading.is_empty() {
        return (
            None,
            vec![ValidationFinding::error(
                "INBOX_DIMENSION_HEADING_MISSING",
                format!("Dimension heading not found for {dimension}"),
            )],
        );
    }
    let Some((section_start, section_end, section)) = locate_dimension_section(content, &heading)
    else {
        return (
            None,
            vec![ValidationFinding::error(
                "INBOX_DIMENSION_HEADING_MISSING",
                format!("Dimension heading not found for {dimension}"),
            )],
        );
    };
    let Some((active_start, inactive_start)) = locate_active_inactive_bounds(&section) else {
        return (
            None,
            vec![ValidationFinding::error(
                "INBOX_DIMENSION_STRUCTURE_INVALID",
                format!("Dimension structure invalid for {heading}"),
            )],
        );
    };
    let active_section = &section[active_start..inactive_start];
    let new_entry = format!("- {value}\n  - {context}");
    let updated_active = if active_section.contains("(No active entries.)") {
        active_section.replacen("(No active entries.)", &new_entry, 1)
    } else {
        format!("{}\n\n{}\n", active_section.trim_end(), new_entry)
    };
    let updated_section = format!(
        "{}{}{}",
        &section[..active_start],
        updated_active,
        &section[inactive_start..]
    );
    let updated_content = format!(
        "{}{}{}",
        &content[..section_start],
        updated_section,
        &content[section_end..]
    );
    (
        Some(DimensionAppendPlan {
            updated_content,
            anchor: heading.trim_start_matches("## ").to_string(),
        }),
        Vec::new(),
    )
}

fn escape_json(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
}

fn slugify(value: &str) -> String {
    let mut slug = String::new();
    let mut previous_dash = false;
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() {
            slug.push(ch.to_ascii_lowercase());
            previous_dash = false;
        } else if !previous_dash {
            slug.push('-');
            previous_dash = true;
        }
    }
    let trimmed = slug.trim_matches('-').to_string();
    if trimmed.is_empty() {
        "pattern".to_string()
    } else {
        trimmed
    }
}

fn extract_operation_state_entry(
    state_json: &str,
    bucket: &str,
    findings: &mut Vec<ValidationFinding>,
) -> OperationStateEntry {
    let marker = format!("\"{bucket}\": {{");
    let Some(start) = state_json.find(&marker) else {
        findings.push(ValidationFinding::warning(
            "OPERATIONS_STATE_INVALID",
            format!("Operations state is missing `{bucket}` entry"),
        ));
        return default_operation_state_entry();
    };
    let slice = &state_json[start + marker.len()..];
    let Some(end) = slice.find('}') else {
        findings.push(ValidationFinding::warning(
            "OPERATIONS_STATE_INVALID",
            format!("Operations state entry `{bucket}` is malformed"),
        ));
        return default_operation_state_entry();
    };
    let section = &slice[..end];
    OperationStateEntry {
        status: extract_json_string(section, "status").unwrap_or_else(|| "idle".to_string()),
        last_started: extract_json_string(section, "last_started").unwrap_or_default(),
        last_completed: extract_json_string(section, "last_completed").unwrap_or_default(),
        last_report_target: extract_json_string(section, "last_report_target").unwrap_or_default(),
        last_error: extract_json_string(section, "last_error").unwrap_or_default(),
        requested_by: extract_json_string(section, "requested_by").unwrap_or_default(),
        run_count: extract_json_u32(section, "run_count").unwrap_or(0),
    }
}

fn inventory_role_for_growth_target(root: &Path, target: &str) -> String {
    let (entries, _, _) = discover_matrix_inventory(root);
    if let Some(entry) = entries.into_iter().find(|item| item.path == target) {
        return entry.inventory_role;
    }
    let target_path = root.join(target);
    if let Ok(content) = fs::read_to_string(&target_path) {
        if content.contains("Hub Source of Truth") {
            return "dimension-hub".to_string();
        }
        if content.contains("Identity Source of Truth") || content.contains("## 100.WHO.Identity") {
            return "agent-identity".to_string();
        }
        if content.contains("Cornerstone Source of Truth") {
            return "cornerstone".to_string();
        }
    }
    inferred_inventory_role_for_path(target)
        .unwrap_or("branch-sot")
        .to_string()
}

fn sanitize_growth_stem(value: &str) -> String {
    let mut result = String::new();
    let mut previous_dash = false;
    for ch in value.chars() {
        let allowed = ch.is_ascii_alphanumeric() || matches!(ch, '.' | '-');
        if allowed {
            result.push(ch);
            previous_dash = false;
        } else if !previous_dash {
            result.push('-');
            previous_dash = true;
        }
    }
    result.trim_matches('-').to_string()
}

fn numbered_reference_target(
    root: &Path,
    assessed_target: &str,
    subject_hint: &str,
) -> Option<String> {
    let name = Path::new(assessed_target).file_name()?.to_str()?;
    let parent_id = matrix_numeric_id_for_name(name)?;
    let ref_id = next_available_ref_id(root, &parent_id)?;
    let context = matrix_context_for_name(name)?;
    let subject = growth_subject_from_hint_or_source(name, subject_hint)?;
    Some(format!("knowledge/{ref_id}.{context}.{subject}-Ref.md"))
}

fn numbered_spawn_target(root: &Path, assessed_target: &str, subject_hint: &str) -> Option<String> {
    let name = Path::new(assessed_target).file_name()?.to_str()?;
    let source_id = matrix_numeric_id_for_name(name)?;
    let source_kind = matrix_id_kind_for_name(name)?;
    let subject = spawn_subject_for_source(name, subject_hint)?;

    match source_kind {
        "hub" => {
            let hub_id = hub_id_for_numeric_id(&source_id)?;
            let child_id = next_available_direct_child_id(root, &hub_id)?;
            let context = hub_context_for_numeric_id(&source_id)?;
            Some(format!("knowledge/{child_id}.{context}.{subject}-SoT.md"))
        }
        "direct-child" => {
            let child_id = next_available_grandchild_id(root, &source_id)?;
            let context = child_context_for_source(name)?;
            Some(format!("knowledge/{child_id}.{context}.{subject}-SoT.md"))
        }
        "grandchild" => {
            let hub_id = hub_id_for_numeric_id(&source_id)?;
            let child_id = next_available_direct_child_id(root, &hub_id)?;
            let context = hub_context_for_numeric_id(&source_id)?;
            Some(format!("knowledge/{child_id}.{context}.{subject}-SoT.md"))
        }
        _ => None,
    }
}

fn spawned_parent_link(execution_target: &str) -> Option<String> {
    let name = Path::new(execution_target).file_name()?.to_str()?;
    let numeric_id = matrix_numeric_id_for_name(name)?;
    match hub_id_for_numeric_id(&numeric_id)?.as_str() {
        "100" => Some("[[100.WHO.Circle-SoT#100.WHO.Humans-and-Agents]]".to_string()),
        "200" => Some("[[200.WHAT.Domain-SoT#200.WHAT.Domains]]".to_string()),
        "300" => Some("[[300.WHERE.Terrain-SoT#300.WHERE.Terrain]]".to_string()),
        "400" => Some("[[400.WHEN.Chronicle-SoT#400.WHEN.Chronicle]]".to_string()),
        "500" => Some("[[500.HOW.Method-SoT#500.HOW.Method]]".to_string()),
        "600" => Some("[[600.WHY.Compass-SoT#600.WHY.Compass]]".to_string()),
        _ => None,
    }
}

fn normalize_subject_root(subject: &str) -> String {
    let normalized = subject
        .strip_suffix("-Identity")
        .or_else(|| subject.strip_suffix("-Capabilities"))
        .or_else(|| subject.strip_suffix("-Intent"))
        .unwrap_or(subject);
    sanitize_growth_stem(normalized)
}

fn child_context_for_source(name: &str) -> Option<String> {
    let subject = matrix_subject_for_name(name)?;
    let root = normalize_subject_root(&subject);
    if root.is_empty() {
        return None;
    }
    Some(root.to_ascii_uppercase())
}

fn growth_subject_from_hint_or_source(name: &str, subject_hint: &str) -> Option<String> {
    let hinted = sanitize_growth_stem(subject_hint);
    if !hinted.is_empty() {
        return Some(hinted);
    }
    let subject = normalize_subject_root(&matrix_subject_for_name(name)?);
    if subject.is_empty() {
        return None;
    }
    Some(subject)
}

fn spawn_subject_for_source(name: &str, subject_hint: &str) -> Option<String> {
    let kind = matrix_id_kind_for_name(name)?;
    let hinted = sanitize_growth_stem(subject_hint);
    if !hinted.is_empty() {
        return Some(hinted);
    }
    let subject = growth_subject_from_hint_or_source(name, "")?;
    if subject.is_empty() {
        return None;
    }
    match kind {
        "hub" => Some(format!("{subject}-Child")),
        "direct-child" => Some(format!("{subject}-Child")),
        "grandchild" => Some(subject),
        _ => Some(subject),
    }
}

fn today_utc() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs() as i64)
        .unwrap_or(0);
    civil_from_days(seconds.div_euclid(86_400))
}

fn extract_reference_targets(text: &str) -> Vec<String> {
    let mut targets = Vec::new();
    let mut remaining = text;
    while let Some(start) = remaining.find("[[") {
        let after_start = &remaining[start + 2..];
        let Some(end) = after_start.find("]]") else {
            break;
        };
        let raw = &after_start[..end];
        let target = raw.split('#').next().unwrap_or("").trim();
        if target.ends_with("-Ref") {
            targets.push(target.to_string());
        }
        remaining = &after_start[end + 2..];
    }
    targets.sort();
    targets.dedup();
    targets
}

fn replace_ref_with_sot_pointer(text: &str, ref_target: &str, sot_target: &str) -> String {
    text.replace(
        &format!("[[{}]]", stem_or_empty(ref_target)),
        &format!("[[{}]]", stem_or_empty(sot_target)),
    )
}

fn civil_from_days(days_since_epoch: i64) -> String {
    let z = days_since_epoch + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = mp + if mp < 10 { 3 } else { -9 };
    let year = y + if m <= 2 { 1 } else { 0 };
    format!("{year:04}-{m:02}-{d:02}")
}

fn dimension_entry_counts(text: &str) -> Vec<usize> {
    let mut counts = BTreeMap::new();
    let mut current_dimension = String::new();
    for raw_line in text.lines() {
        let line = raw_line.trim();
        if let Some(prefix) = line.strip_prefix("## ") {
            let dimension = prefix.split('.').next().unwrap_or_default();
            if matches!(dimension, "100" | "200" | "300" | "400" | "500" | "600") {
                current_dimension = dimension.to_string();
                counts.entry(current_dimension.clone()).or_insert(0);
            } else {
                current_dimension.clear();
            }
            continue;
        }
        if !current_dimension.is_empty() && raw_line.starts_with("- ") {
            *counts.entry(current_dimension.clone()).or_insert(0) += 1;
        }
    }
    counts.into_values().collect()
}

fn is_subgroup_heading(line: &str) -> bool {
    let Some(rest) = line.trim().strip_prefix("## ") else {
        return false;
    };
    let mut parts = rest.split('.');
    let Some(number) = parts.next() else {
        return false;
    };
    number.len() == 3
        && number.chars().all(|ch| ch.is_ascii_digit())
        && matches!(
            number.chars().next(),
            Some('1' | '2' | '3' | '4' | '5' | '6')
        )
        && number.ends_with('0')
        && !matches!(number, "100" | "200" | "300" | "400" | "500" | "600")
}

fn extract_reference_entries(source_text: &str) -> (String, Vec<String>) {
    let counts = dimension_entry_counts_by_id(source_text);
    if counts.is_empty() {
        return (String::new(), Vec::new());
    }
    let densest = counts
        .keys()
        .max_by_key(|dimension| {
            (
                counts.get(*dimension).copied().unwrap_or_default(),
                dimension_preference(dimension),
            )
        })
        .cloned()
        .unwrap_or_default();
    let heading = dimension_heading(source_text, &densest);
    let section = section_by_heading(source_text, &heading);
    let active = subsection(section.as_str(), "### Active");
    (
        heading,
        entry_blocks(active.as_str()).into_iter().take(2).collect(),
    )
}

fn locate_dimension_section(
    content: &str,
    dimension_heading: &str,
) -> Option<(usize, usize, String)> {
    let section_start = content.find(dimension_heading)?;
    let next_section = content[section_start + 1..]
        .find("\n## ")
        .map(|offset| section_start + 1 + offset)
        .unwrap_or(content.len());
    Some((
        section_start,
        next_section,
        content[section_start..next_section].to_string(),
    ))
}

fn append_line_to_section(text: &str, heading: &str, addition: &str) -> String {
    if addition.trim().is_empty() {
        return text.to_string();
    }
    let Some(start) = text.find(heading) else {
        return text.to_string();
    };
    let rest = &text[start + heading.len()..];
    let end = rest
        .find("\n### ")
        .or_else(|| rest.find("\n## "))
        .map(|offset| start + heading.len() + offset)
        .unwrap_or(text.len());
    let section = text[start..end].trim_end_matches('\n');
    if section.contains(addition) {
        return text.to_string();
    }
    let replacement = format!("{section}\n\n{addition}\n");
    format!("{}{}{}", &text[..start], replacement, &text[end..])
}

fn locate_active_inactive_bounds(section: &str) -> Option<(usize, usize)> {
    let active_start = section.find("### Active")?;
    let inactive_start = section.find("### Inactive")?;
    Some((active_start, inactive_start))
}

fn extract_entry_block(section: &str, entry_value: &str) -> Option<String> {
    let lines: Vec<&str> = section.lines().collect();
    let marker = format!("- {entry_value}");
    let start_index = lines.iter().position(|line| line.trim() == marker)?;
    let mut block = Vec::new();
    for line in &lines[start_index..] {
        if line.starts_with("- ") && !block.is_empty() {
            break;
        }
        if line.starts_with("### ") && !block.is_empty() {
            break;
        }
        if line.starts_with("## ") && !block.is_empty() {
            break;
        }
        block.push((*line).to_string());
    }
    Some(block.join("\n").trim().to_string())
}

fn dimension_entry_counts_by_id(text: &str) -> BTreeMap<String, usize> {
    let mut counts = BTreeMap::new();
    let mut current_dimension = String::new();
    for raw_line in text.lines() {
        let line = raw_line.trim();
        if let Some(prefix) = line.strip_prefix("## ") {
            let dimension = prefix.split('.').next().unwrap_or_default();
            if matches!(dimension, "100" | "200" | "300" | "400" | "500" | "600") {
                current_dimension = dimension.to_string();
                counts.entry(current_dimension.clone()).or_insert(0);
            } else {
                current_dimension.clear();
            }
            continue;
        }
        if !current_dimension.is_empty() && raw_line.starts_with("- ") {
            *counts.entry(current_dimension.clone()).or_insert(0) += 1;
        }
    }
    counts
}

fn dimension_preference(dimension: &str) -> usize {
    match dimension {
        "200" => 6,
        "500" => 5,
        "300" => 4,
        "400" => 3,
        "600" => 2,
        "100" => 1,
        _ => 0,
    }
}

fn dimension_heading(text: &str, dimension: &str) -> String {
    text.lines()
        .find(|line| {
            let trimmed = line.trim();
            trimmed.starts_with("## ") && trimmed.starts_with(&format!("## {dimension}."))
        })
        .unwrap_or("")
        .to_string()
}

fn dimension_label(text: &str, dimension: &str) -> String {
    let heading = dimension_heading(text, dimension);
    let parts: Vec<&str> = heading.split('.').collect();
    if parts.len() < 3 {
        return "Grouping".to_string();
    }
    let raw = parts[2..].join(".");
    let mut cleaned = String::new();
    let mut previous_dash = false;
    for ch in raw.chars() {
        if ch.is_ascii_alphanumeric() {
            cleaned.push(ch);
            previous_dash = false;
        } else if !previous_dash {
            cleaned.push('-');
            previous_dash = true;
        }
    }
    let trimmed = cleaned.trim_matches('-').to_string();
    if trimmed.is_empty() {
        "Grouping".to_string()
    } else {
        trimmed
    }
}

fn next_top_level_heading_for_dimension(text: &str, dimension: &str) -> String {
    let current = dimension.parse::<usize>().unwrap_or_default();
    for candidate in ((current + 100)..=700).step_by(100) {
        let marker = format!("## {candidate:03}.");
        if let Some(start) = text.find(&marker) {
            let end = text[start..]
                .find('\n')
                .map(|offset| start + offset)
                .unwrap_or(text.len());
            return text[start..end].to_string();
        }
    }
    String::new()
}

fn section_by_heading(text: &str, heading: &str) -> String {
    if heading.is_empty() {
        return String::new();
    }
    let Some(start) = text.find(heading) else {
        return String::new();
    };
    let rest = &text[start + heading.len()..];
    let end = rest
        .find("\n## ")
        .map(|offset| start + heading.len() + offset)
        .unwrap_or(text.len());
    text[start..end].to_string()
}

fn replace_entries_with_reference_pointer(
    source_text: &str,
    dimension_heading: &str,
    entries: &[String],
    pointer: &str,
) -> String {
    if dimension_heading.is_empty() || entries.is_empty() {
        return source_text.to_string();
    }
    let section = section_by_heading(source_text, dimension_heading);
    if section.is_empty() {
        return source_text.to_string();
    }
    let active = subsection(section.as_str(), "### Active");
    let mut updated_active = active.clone();
    for entry in entries {
        updated_active = updated_active.replace(entry, "").trim().to_string();
    }
    if !updated_active.contains(pointer) {
        updated_active = format!("{}\n\n{}", updated_active.trim(), pointer)
            .trim()
            .to_string();
    }
    let section_updated = section.replacen(active.as_str(), &updated_active, 1);
    source_text.replacen(section.as_str(), &section_updated, 1)
}

fn subsection(section: &str, heading: &str) -> String {
    let Some(start) = section.find(heading) else {
        return String::new();
    };
    let rest = &section[start + heading.len()..];
    let end = rest
        .find("\n### ")
        .or_else(|| rest.find("\n## "))
        .map(|offset| start + heading.len() + offset)
        .unwrap_or(section.len());
    section[start..end].to_string()
}

fn insert_spawn_branch_pointer(
    source_text: &str,
    dimension_heading: &str,
    pointer: &str,
) -> String {
    if dimension_heading.is_empty() || pointer.trim().is_empty() {
        return source_text.to_string();
    }
    let section = section_by_heading(source_text, dimension_heading);
    if section.is_empty() {
        return source_text.to_string();
    }
    let active = subsection(section.as_str(), "### Active");
    let updated_active = if active.contains(pointer) {
        active
    } else {
        format!("{}\n\n{}\n", active.trim_end(), pointer)
    };
    let section_updated = section.replacen(
        subsection(section.as_str(), "### Active").as_str(),
        &updated_active,
        1,
    );
    source_text.replacen(section.as_str(), &section_updated, 1)
}

fn entry_blocks(section: &str) -> Vec<String> {
    let mut blocks = Vec::new();
    let mut current = Vec::new();
    for line in section.lines() {
        if line.starts_with("- ") {
            if !current.is_empty() {
                blocks.push(current.join("\n"));
                current.clear();
            }
            current.push(line.to_string());
            continue;
        }
        if line.starts_with("  - ") && !current.is_empty() {
            current.push(line.to_string());
            continue;
        }
        if !current.is_empty() && line.trim().is_empty() {
            current.push(line.to_string());
        }
    }
    if !current.is_empty() {
        while current.last().is_some_and(|line| line.trim().is_empty()) {
            current.pop();
        }
        if !current.is_empty() {
            blocks.push(current.join("\n"));
        }
    }
    blocks
}

fn extract_bucket_entries(registry_json: &str, bucket: &str) -> Vec<DreamerAction> {
    let marker = format!("\"{bucket}\": [");
    let Some(start) = registry_json.find(&marker) else {
        return Vec::new();
    };
    let slice = &registry_json[start + marker.len()..];
    let Some(end) = slice.find(']') else {
        return Vec::new();
    };
    let section = &slice[..end];
    let mut matches = Vec::new();
    for object in section.split("},") {
        let pattern_reason = extract_json_string(object, "pattern_reason").unwrap_or_default();
        let status = extract_json_string(object, "status").unwrap_or_default();
        if !pattern_reason.is_empty() || !status.is_empty() {
            matches.push(DreamerAction {
                follow_up_target: extract_json_string(object, "follow_up_target")
                    .unwrap_or_default(),
                execution_target: extract_json_string(object, "execution_target")
                    .unwrap_or_default(),
                pattern_reason,
                actor: extract_json_string(object, "actor").unwrap_or_default(),
                execution_reason: extract_json_string(object, "execution_reason")
                    .unwrap_or_default(),
                applied_at: extract_json_string(object, "applied_at").unwrap_or_default(),
                status,
            });
        }
    }
    matches
}

fn extract_json_string(text: &str, key: &str) -> Option<String> {
    let marker = format!("\"{key}\":");
    let start = text.find(&marker)? + marker.len();
    let remainder = text[start..].trim_start();
    let remainder = remainder.strip_prefix('"')?;
    let end = remainder.find('"')?;
    Some(remainder[..end].to_string())
}

fn extract_json_u32(text: &str, key: &str) -> Option<u32> {
    let marker = format!("\"{key}\":");
    let start = text.find(&marker)? + marker.len();
    let remainder = text[start..].trim_start();
    let end = remainder
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(remainder.len());
    remainder[..end].parse::<u32>().ok()
}

fn extract_json_number(text: &str, key: &str) -> Option<usize> {
    let marker = format!("\"{key}\":");
    let start = text.find(&marker)? + marker.len();
    let remainder = text[start..].trim_start();
    let end = remainder
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(remainder.len());
    remainder[..end].parse::<usize>().ok()
}

fn extract_object_blocks(text: &str) -> Vec<String> {
    let mut blocks = Vec::new();
    let mut depth = 0usize;
    let mut start: Option<usize> = None;
    let mut in_string = false;
    let mut escaped = false;
    for (index, ch) in text.char_indices() {
        if in_string {
            if escaped {
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                in_string = false;
            }
            continue;
        }
        match ch {
            '"' => in_string = true,
            '{' => {
                if depth == 0 {
                    start = Some(index);
                }
                depth += 1;
            }
            '}' => {
                if depth == 0 {
                    continue;
                }
                depth -= 1;
                if depth == 0 {
                    if let Some(begin) = start.take() {
                        blocks.push(text[begin..=index].to_string());
                    }
                }
            }
            _ => {}
        }
    }
    blocks
}

fn extract_json_map_entries(text: &str) -> Vec<(String, usize)> {
    let trimmed = text.trim();
    if trimmed.len() < 2 || !trimmed.starts_with('{') || !trimmed.ends_with('}') {
        return Vec::new();
    }
    let inner = &trimmed[1..trimmed.len() - 1];
    let mut entries = Vec::new();
    for pair in inner.split(',') {
        let piece = pair.trim();
        if piece.is_empty() {
            continue;
        }
        let Some((key, value)) = piece.split_once(':') else {
            continue;
        };
        let key = key.trim().trim_matches('"').to_string();
        let value = value.trim().parse::<usize>().ok();
        if let Some(number) = value {
            entries.push((key, number));
        }
    }
    entries.sort_by(|left, right| left.0.cmp(&right.0));
    entries
}

fn extract_json_string_list(text: &str) -> Vec<String> {
    let trimmed = text.trim();
    if trimmed.len() < 2 || !trimmed.starts_with('[') || !trimmed.ends_with(']') {
        return Vec::new();
    }
    let inner = &trimmed[1..trimmed.len() - 1];
    if inner.trim().is_empty() {
        return Vec::new();
    }
    inner
        .split(',')
        .filter_map(|part| {
            let item = part.trim().trim_matches('"');
            if item.is_empty() {
                None
            } else {
                Some(item.to_string())
            }
        })
        .collect()
}

fn missing_shape_findings(content: &str, required: &[&str], code: &str) -> Vec<ValidationFinding> {
    let missing: Vec<&str> = required
        .iter()
        .copied()
        .filter(|item| !content.contains(item))
        .collect();
    if missing.is_empty() {
        Vec::new()
    } else {
        vec![ValidationFinding::error(
            code,
            format!(
                "Missing required operational artifact sections: {}",
                missing.join(", ")
            ),
        )]
    }
}

fn meaningful_tokens(value: &str) -> Vec<String> {
    let stopwords = [
        "the", "and", "for", "with", "that", "this", "from", "into", "through", "when", "then",
        "than", "path", "change", "review", "blocked", "reason",
    ];
    let mut tokens: Vec<String> = Vec::new();
    for token in value
        .to_lowercase()
        .split(|c: char| !c.is_ascii_alphanumeric())
        .filter(|token| token.len() > 3 && !stopwords.contains(token))
    {
        if !tokens.iter().any(|item| item == token) {
            tokens.push(token.to_string());
        }
    }
    tokens
}

fn subject_declaration_block(text: &str) -> String {
    let mut inside = false;
    let mut block: Vec<&str> = Vec::new();
    for line in text.lines() {
        if line.trim() == "### Subject Declaration" {
            inside = true;
            block.push(line);
            continue;
        }
        if inside && line.starts_with("### ") {
            break;
        }
        if inside && line.starts_with("## ") && line.trim() != "## 000.Index" {
            break;
        }
        if inside {
            block.push(line);
        }
    }
    block.join("\n").trim().to_string()
}

fn archive_postcondition_failure(
    content: &str,
    entry_value: &str,
    archived_reason: &str,
    dimension_heading: &str,
) -> Option<String> {
    let section_start = content.find(dimension_heading)?;
    let next_section = content[section_start + 1..]
        .find("\n## ")
        .map(|position| section_start + 1 + position)
        .unwrap_or(content.len());
    let section = &content[section_start..next_section];
    let active_start = section.find("### Active")?;
    let inactive_start = section.find("### Inactive")?;
    let active = &section[active_start..inactive_start];
    let inactive = &section[inactive_start..];
    let marker = format!("- {entry_value}");

    if active.contains(&marker) {
        return Some("Entry still appears in Active after archive transaction".to_string());
    }
    if !inactive.contains(&marker)
        || !inactive.contains(&format!("Archived Reason: {archived_reason}"))
    {
        return Some(
            "Entry does not appear in Inactive with archived metadata after archive transaction"
                .to_string(),
        );
    }

    let archive_start = content.find("## 700.Archive")?;
    let archive_section = &content[archive_start..];
    if !archive_section.contains(&format!("FROM: {dimension_heading}"))
        || !archive_section.contains(&marker)
    {
        return Some(
            "Entry does not appear in 700.Archive with timestamp and source after archive transaction"
                .to_string(),
        );
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn routes_inbox_entries_by_first_match() {
        assert_eq!(
            route_inbox_entry("Alex joined the project team this week."),
            Some("100")
        );
        assert_eq!(
            route_inbox_entry("We chose Fidelity because of NAV DRIP."),
            Some("600")
        );
        assert_eq!(route_inbox_entry("Unsorted note needing review."), None);
    }

    #[test]
    fn detects_subject_declaration_changes() {
        let before =
            "## 000.Index\n\n### Subject Declaration\n\n**Subject:** Before\n\n### Links\n";
        let after = "## 000.Index\n\n### Subject Declaration\n\n**Subject:** After\n\n### Links\n";
        let findings = validate_subject_declaration_change(before, after, false);
        assert!(findings
            .iter()
            .any(|item| item.code == "SUBJECT_DECLARATION_APPROVAL_REQUIRED"));
    }

    #[test]
    fn requires_approval_for_spawn_stage() {
        let findings = validate_growth_stage("spawn", false);
        assert!(findings
            .iter()
            .any(|item| item.code == "SPAWN_APPROVAL_REQUIRED"));
    }

    #[test]
    fn assesses_growth_for_identity_branch() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("repo root")
            .to_path_buf();
        let assessment = assess_growth_target(&root, "knowledge/110.WHO.Vela-Identity-SoT.md");
        assert_eq!(assessment.inventory_role, "agent-identity");
        assert_eq!(assessment.stage, "flat");
        assert!(assessment.exists);
    }

    #[test]
    fn plans_spawn_growth_execution_for_identity_branch() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("repo root")
            .to_path_buf();
        let (plan, findings) = plan_growth_execution(
            &root,
            "spawn",
            "knowledge/110.WHO.Vela-Identity-SoT.md",
            "knowledge/ARTIFACTS/proposals/growth-apply-spawn-test.md",
            "",
        );
        assert!(findings.is_empty());
        let plan = plan.expect("growth plan");
        assert_eq!(plan.kind, "spawned-sot");
        assert_eq!(plan.target, "knowledge/111.VELA.Vela-Child-SoT.md");
    }

    #[test]
    fn plans_spawn_growth_execution_with_subject_hint() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("repo root")
            .to_path_buf();
        let (plan, findings) = plan_growth_execution(
            &root,
            "spawn",
            "knowledge/110.WHO.Vela-Identity-SoT.md",
            "knowledge/ARTIFACTS/proposals/growth-apply-spawn-test.md",
            "Matrix-Crew",
        );
        assert!(findings.is_empty());
        let plan = plan.expect("growth plan");
        assert_eq!(plan.target, "knowledge/111.VELA.Matrix-Crew-SoT.md");
    }

    #[test]
    fn lists_merge_candidates_from_repo_state() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("repo root")
            .to_string_lossy()
            .to_string();
        let items = list_merge_candidates(&root);
        assert!(items.iter().all(|item| item.count >= 3));
    }

    #[test]
    fn plans_spawn_growth_source_update_for_identity_branch() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("repo root")
            .to_path_buf();
        let (plan, findings) = plan_growth_source_update(
            &root,
            "spawn",
            "knowledge/110.WHO.Vela-Identity-SoT.md",
            "knowledge/111.VELA.Vela-Child-SoT.md",
            "knowledge/ARTIFACTS/proposals/growth-apply-spawn-test.md",
        );
        assert!(findings.is_empty());
        let plan = plan.expect("source update plan");
        assert_eq!(plan.target_dimension, "## 200.WHAT.Scope");
        assert!(plan
            .active_pointer_line
            .contains("[[111.VELA.Vela-Child-SoT]]"));
    }

    #[test]
    fn applies_reference_growth_source_update() {
        let source = "# Test\n\n### Links\n\n(None.)\n\n### Status\n\n(None.)\n\n### Next Actions\n\n(None.)\n\n### Decisions\n\n(None.)\n\n## 200.WHAT.Scope\n\n### Active\n\n- One. (2026-04-11)\n  - A.\n- Two. (2026-04-11)\n  - B.\n\n### Inactive\n\n(No inactive entries.)\n";
        let plan = GrowthSourceUpdatePlan {
            link_line: "- Reference Note: [[Ref.Test]]".to_string(),
            status_line: "- Status update. (2026-04-11)\n  - Context. [AGENT:gpt-5]".to_string(),
            next_action_line: "- Next action. (2026-04-11)\n  - Context. [AGENT:gpt-5]".to_string(),
            decision_line: "- [2026-04-11] Decision note.".to_string(),
            target_dimension: "## 200.WHAT.Scope".to_string(),
            replacement_entries: vec![
                "- One. (2026-04-11)\n  - A.".to_string(),
                "- Two. (2026-04-11)\n  - B.".to_string(),
            ],
            active_pointer_line: "- Detailed entries moved to `[[Ref.Test]]`. (2026-04-11)\n  - Pointer context. [AGENT:gpt-5]".to_string(),
        };
        let applied = apply_growth_source_update(source, "reference-note", &plan);
        assert!(applied
            .updated_content
            .contains("Reference Note: [[Ref.Test]]"));
        assert!(applied
            .updated_content
            .contains("Detailed entries moved to `[[Ref.Test]]`."));
        assert!(!applied
            .updated_content
            .contains("- One. (2026-04-11)\n  - A."));
    }

    #[test]
    fn renders_fractalized_growth_source() {
        let source = "# Test\n\n## 100.WHO.Identity\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n## 200.WHAT.Scope\n\n### Active\n\n- One. (2026-04-11)\n  - A.\n- Two. (2026-04-11)\n  - B.\n- Three. (2026-04-11)\n  - C.\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n## 300.WHERE.Place\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n";
        let rendered = render_fractalized_growth_source(
            source,
            "knowledge/ARTIFACTS/proposals/example-growth.md",
            "2026-04-11",
        );
        assert!(rendered.contains("## 210.Scope-Subgroup"));
        assert!(rendered.contains("Grouping scaffold created"));
    }

    #[test]
    fn plans_archive_transaction() {
        let content = "## 100.WHO.Identity\n\n### Active\n\n- Sample value. (2026-04-08)\n  - Sample context.\n\n### Inactive\n\n(No inactive entries.)\n\n## 700.Archive\n\n(No archived entries.)\n";
        let (plan, findings) = plan_archive_transaction(
            content,
            "## 100.WHO.Identity",
            "Sample value. (2026-04-08)",
            "Replaced for test",
            "2026-04-11",
            "202604110300",
        );
        assert!(findings.is_empty());
        let plan = plan.expect("archive plan");
        assert!(plan
            .updated_content
            .contains("Archived Reason: Replaced for test"));
        assert!(plan
            .updated_content
            .contains("[202604110300] FROM: ## 100.WHO.Identity"));
    }

    #[test]
    fn plans_cross_reference_update() {
        let content = "## 100.WHO.Identity\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n";
        let (plan, findings) = plan_cross_reference_update(
            content,
            "## 100.WHO.Identity",
            "Reference target",
            "210.WHAT.Vela-Capabilities-SoT",
            "## 200.WHAT.Scope",
            "2026-04-11",
        );
        assert!(findings.is_empty());
        let plan = plan.expect("cross reference plan");
        assert!(plan
            .pointer
            .contains("[[210.WHAT.Vela-Capabilities-SoT#200.WHAT.Scope]]"));
        assert!(plan.updated_content.contains("Reference target"));
    }

    #[test]
    fn plans_inbox_entry_from_heading_target() {
        let root = Path::new("/home/knosence/vela");
        let text = "# Inbox Item\n\nTarget: [[210.WHAT.Vela-Capabilities-SoT]]\n\nThe framework has three layers.\nIt defines a component clearly.";
        let (plan, findings) = plan_inbox_entry(root, text, "test-inbox-item.md");
        assert!(findings.is_empty());
        let plan = plan.expect("inbox plan");
        assert_eq!(plan.target, "knowledge/210.WHAT.Vela-Capabilities-SoT.md");
        assert_eq!(plan.dimension, "200");
        assert_eq!(plan.value, "The framework has three layers.. (2026-04-10)");
        assert_eq!(plan.context, "It defines a component clearly.");
    }

    #[test]
    fn plans_csv_inbox_entries() {
        let root = Path::new("/home/knosence/vela");
        let text = "# Target: [[220.WHAT.Repo-Watchlist-SoT]]\nvalue,context,dimension\nRepo watch summary recorded,Component release summary,200\n";
        let (plan, findings) = plan_csv_inbox(root, text, "test-inbox-item.csv");
        assert!(findings.is_empty());
        let plan = plan.expect("csv inbox plan");
        assert_eq!(plan.target, "knowledge/220.WHAT.Repo-Watchlist-SoT.md");
        assert_eq!(plan.entries.len(), 1);
        assert_eq!(plan.entries[0].dimension, "200");
        assert_eq!(
            plan.entries[0].value,
            "Repo watch summary recorded. (2026-04-10)"
        );
    }

    #[test]
    fn plans_companion_destination() {
        let root = Path::new("/home/knosence/vela");
        let (plan, findings) = plan_companion_path(
            root,
            "knowledge/INBOX/test-inbox-item.txt",
            "knowledge/ARTIFACTS/proposals/inbox-triage-target.md",
            "20260410",
        );
        assert!(findings.is_empty());
        let plan = plan.expect("companion plan");
        assert_eq!(
            plan.destination,
            "knowledge/ARTIFACTS/proposals/inbox-triage-target.txt"
        );
    }

    #[test]
    fn plans_dimension_append() {
        let content = "## 200.WHAT.Scope\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n";
        let (plan, findings) = plan_dimension_append(
            content,
            "200",
            "Capability update. (2026-04-10)",
            "Captured from inbox.",
        );
        assert!(findings.is_empty());
        let plan = plan.expect("append plan");
        assert!(plan
            .updated_content
            .contains("- Capability update. (2026-04-10)"));
        assert_eq!(plan.anchor, "200.WHAT.Scope");
    }

    #[test]
    fn validates_archive_postconditions() {
        let content = "## 100.WHO.Identity\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n- Sample archived value. (2026-04-08)\n  - Exists to verify archive movement. [AGENT:gpt-5]\n  - Archived: 2026-04-09\n  - Archived Reason: Replaced by newer fact\n\n## 700.Archive\n\n[202604090352] FROM: ## 100.WHO.Identity\n- Sample archived value. (2026-04-08)\n  - Exists to verify archive movement. [AGENT:gpt-5]\n  - Archived: 2026-04-09\n  - Archived Reason: Replaced by newer fact\n";
        let findings = validate_archive_postconditions(
            content,
            "Sample archived value. (2026-04-08)",
            "Replaced by newer fact",
            "## 100.WHO.Identity",
        );
        assert!(findings.is_empty());
    }

    #[test]
    fn matches_validator_actions_from_registry() {
        let registry = r#"{
  "validator_changes": [
    {
      "follow_up_target": "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.validator.md",
      "execution_target": "knowledge/ARTIFACTS/refs/Dreamer-Execution.validator.md",
      "pattern_reason": "frontmatter structure validation",
      "actor": "human",
      "execution_reason": "tighten validator behavior",
      "applied_at": "2026-04-09T00:00:00+00:00",
      "status": "active"
    }
  ],
  "workflow_changes": [],
  "refusal_tightenings": []
}"#;
        let matches = match_dreamer_actions(
            registry,
            "validator",
            "knowledge/210.WHAT.Vela-Capabilities-SoT.md",
            "test",
            "validator structure check",
            "frontmatter structure validation matters here",
        );
        assert_eq!(matches.len(), 1);
        assert_eq!(
            matches[0].pattern_reason,
            "frontmatter structure validation"
        );
    }

    #[test]
    fn matches_refusal_actions_from_registry() {
        let registry = r#"{
  "validator_changes": [],
  "workflow_changes": [],
  "refusal_tightenings": [
    {
      "follow_up_target": "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.refusal.md",
      "execution_target": "knowledge/ARTIFACTS/refs/Dreamer-Execution.refusal.md",
      "pattern_reason": "cross reference pointer",
      "actor": "human",
      "execution_reason": "tighten refusal behavior",
      "applied_at": "2026-04-09T00:00:00+00:00",
      "status": "active"
    }
  ]
}"#;
        let matches = match_dreamer_actions(
            registry,
            "refusal",
            "knowledge/ARTIFACTS/proposals/test.md",
            "cross-reference",
            "cross reference pointer update",
            "Cross reference pointer write.",
        );
        assert_eq!(matches.len(), 1);
        assert_eq!(matches[0].pattern_reason, "cross reference pointer");
    }

    #[test]
    fn parses_dreamer_action_registry() {
        let registry = r#"{
  "validator_changes": [
    {
      "follow_up_target": "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.validator.md",
      "execution_target": "knowledge/ARTIFACTS/refs/Dreamer-Execution.validator.md",
      "pattern_reason": "frontmatter structure validation",
      "actor": "human",
      "execution_reason": "tighten validator behavior",
      "applied_at": "2026-04-09T00:00:00+00:00",
      "status": "active"
    }
  ],
  "workflow_changes": [],
  "refusal_tightenings": []
}"#;
        let (parsed, findings) = parse_dreamer_action_registry(registry);
        assert!(findings.is_empty());
        assert_eq!(parsed.validator_changes.len(), 1);
        assert_eq!(
            parsed.validator_changes[0].execution_target,
            "knowledge/ARTIFACTS/refs/Dreamer-Execution.validator.md"
        );
    }

    #[test]
    fn registers_dreamer_action() {
        let registry = r#"{
  "validator_changes": [],
  "workflow_changes": [],
  "refusal_tightenings": []
}"#;
        let (updated, findings) = register_dreamer_action(
            registry,
            "workflow",
            DreamerAction {
                follow_up_target: "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.workflow.md"
                    .to_string(),
                execution_target: "knowledge/ARTIFACTS/refs/Dreamer-Execution.workflow.md"
                    .to_string(),
                pattern_reason: "triage route queue".to_string(),
                actor: "human".to_string(),
                execution_reason: "tighten routing".to_string(),
                applied_at: "2026-04-09T00:00:00+00:00".to_string(),
                status: "active".to_string(),
            },
        );
        assert!(findings.is_empty());
        assert_eq!(updated.workflow_changes.len(), 1);
    }

    #[test]
    fn updates_dreamer_action_status() {
        let registry = r#"{
  "validator_changes": [],
  "workflow_changes": [
    {
      "follow_up_target": "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.workflow.md",
      "execution_target": "knowledge/ARTIFACTS/refs/Dreamer-Execution.workflow.md",
      "pattern_reason": "triage route queue",
      "actor": "human",
      "execution_reason": "tighten routing",
      "applied_at": "2026-04-09T00:00:00+00:00",
      "status": "active"
    }
  ],
  "refusal_tightenings": []
}"#;
        let (updated, findings) = update_dreamer_action_status(
            registry,
            "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.workflow.md",
            "inactive",
        );
        assert!(findings.is_empty());
        assert_eq!(updated.workflow_changes[0].status, "inactive");
    }

    #[test]
    fn operations_state_updates_runs_through_rust_core() {
        let (running_state, running_findings) = update_operations_state(
            "{}",
            "patrol",
            "running",
            "human",
            Some("2026-04-10T10:00:00Z"),
            None,
            None,
            Some(""),
            false,
        );
        let _ = running_findings;

        let running_state_json = format!(
            "{{\"patrol\":{{\"status\":\"{}\",\"last_started\":\"{}\",\"last_completed\":\"{}\",\"last_report_target\":\"{}\",\"last_error\":\"{}\",\"requested_by\":\"{}\",\"run_count\":{}}},\"night-cycle\":{{\"status\":\"{}\",\"last_started\":\"{}\",\"last_completed\":\"{}\",\"last_report_target\":\"{}\",\"last_error\":\"{}\",\"requested_by\":\"{}\",\"run_count\":{}}}}}",
            running_state.patrol.status,
            running_state.patrol.last_started,
            running_state.patrol.last_completed,
            running_state.patrol.last_report_target,
            running_state.patrol.last_error,
            running_state.patrol.requested_by,
            running_state.patrol.run_count,
            running_state.night_cycle.status,
            running_state.night_cycle.last_started,
            running_state.night_cycle.last_completed,
            running_state.night_cycle.last_report_target,
            running_state.night_cycle.last_error,
            running_state.night_cycle.requested_by,
            running_state.night_cycle.run_count,
        );
        let (state, findings) = update_operations_state(
            &running_state_json,
            "patrol",
            "completed",
            "human",
            None,
            Some("2026-04-10T10:10:00Z"),
            Some("knowledge/ARTIFACTS/refs/Warden-Patrol-20260410-1010.md"),
            Some(""),
            true,
        );
        let _ = findings;
        assert_eq!(state.patrol.status, "completed");
        assert_eq!(state.patrol.requested_by, "human");
        assert_eq!(state.patrol.run_count, 1);
    }

    #[test]
    fn malformed_operation_lock_is_rejected() {
        let (_, findings) = validate_operation_lock("{}", "patrol");
        assert!(findings
            .iter()
            .any(|item| item.code == "OPERATION_LOCK_INVALID"));
    }

    #[test]
    fn operation_request_rejects_disallowed_actor() {
        let findings = validate_operation_request("patrol", "vela");
        assert!(findings
            .iter()
            .any(|item| item.code == "OPERATION_REQUEST_NOT_ALLOWED"));
    }

    #[test]
    fn operation_transition_rejects_invalid_completion_jump() {
        let findings = validate_operation_state_transition("idle", "completed");
        assert!(findings
            .iter()
            .any(|item| item.code == "OPERATION_STATE_TRANSITION_INVALID"));
    }

    #[test]
    fn dreamer_review_rejects_invalid_decision() {
        let findings = validate_dreamer_review("proposed", "ship-it");
        assert!(findings
            .iter()
            .any(|item| item.code == "DREAMER_REVIEW_DECISION_INVALID"));
    }

    #[test]
    fn dreamer_follow_up_apply_rejects_invalid_actor() {
        let findings = validate_dreamer_follow_up_apply("proposed", "vela");
        assert!(findings
            .iter()
            .any(|item| item.code == "DREAMER_FOLLOW_UP_ACTOR_NOT_ALLOWED"));
    }

    #[test]
    fn classifies_dreamer_follow_up_kind() {
        assert_eq!(
            classify_dreamer_follow_up("validator structure regression"),
            "validator-change"
        );
        assert_eq!(
            classify_dreamer_follow_up("workflow queue routing drift"),
            "workflow-change"
        );
        assert_eq!(
            classify_dreamer_follow_up("need tighter refusal behavior"),
            "refusal-tightening"
        );
    }

    #[test]
    fn rejects_invalid_dreamer_follow_up_kind() {
        let findings = validate_dreamer_follow_up_kind("sandbox-change");
        assert!(findings
            .iter()
            .any(|item| item.code == "DREAMER_FOLLOW_UP_KIND_INVALID"));
    }

    #[test]
    fn validates_dreamer_execution_shape() {
        let findings = validate_dreamer_execution_artifact(
            "# Dreamer Execution\n\n## This Reference Records the Concrete Queue Item Opened from an Approved Dreamer Follow Up\n\n## Classification\n\n- kind: `workflow-change`\n- pattern: `workflow queue`\n- queue: `[[Workflow-Change-Queue]]`\n\n## Execution\n\n- reason: tighten workflow\n- next step: implement.\n",
        );
        assert!(findings.is_empty());
    }

    #[test]
    fn validates_patrol_report_shape() {
        let findings = validate_warden_patrol_report(
            "# Warden Patrol Report\n\n## This Report Records the Latest Patrol Validation Pass Over Recent Day Shift Activity\n\n## Checked Targets\n\n- One\n\n## Structural Flags\n\n- None\n\n## Cosmetic Fixes\n\n- None\n",
        );
        assert!(findings.is_empty());
    }
}
