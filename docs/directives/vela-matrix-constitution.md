# Vela Matrix Constitution

## This Constitution Maps the Universal Matrix Framework Onto Knosence's Shared Knowledge Jurisdiction
The Matrix build kit is the governing framework. Project Vela is one governed domain inside Knosence's repository and shared matrix. Where the framework speaks universally, this constitution states how this repository obeys it concretely.

## This Constitution Establishes the Human Root, Registry, and Sovereign Surfaces
The single cornerstone is [Cornerstone.Knosence-SoT.md](/home/knosence/vela/knowledge/Cornerstone.Knosence-SoT.md). The top-level registry is [Index.Knosence-Matrix-Ref.md](/home/knosence/vela/knowledge/ARTIFACTS/refs/Index.Knosence-Matrix-Ref.md). Sovereign surfaces include the cornerstone, identity SoTs, the canonical watchlist SoT, and local matrix laws.

## This Constitution Keeps Sources of Truth Flat and Moves Operational Exhaust Elsewhere
Canonical SoTs live directly under [knowledge](/home/knosence/vela/knowledge). Non-canonical artifacts such as refs, proposals, logs, archives, and templates live under [ARTIFACTS](/home/knosence/vela/knowledge/ARTIFACTS), and intake lands in [INBOX](/home/knosence/vela/knowledge/INBOX).

## This Constitution Registers Governed References Without Confusing Them for Sources of Truth
SoTs remain the constitutional tree. Governed references such as release-intelligence refs are indexed as review surfaces with explicit parents, but they do not become root authorities or substitute for a SoT.

## This Constitution Applies the Creational Patterns to the Repository Tree
Pattern 1 Canonical Reference means each system or profile subject gets one canonical SoT file.
Pattern 2 Demand-Driven Dimensions means every SoT carries the full structural skeleton even when some dimensions stay sparse.
Pattern 3 Single Parent means every non-cornerstone SoT must declare exactly one parent in frontmatter.
Pattern 4 Identity Lock means dimension identities stay fixed even if the local names evolve.

## This Constitution Applies the Structural Patterns to the Inside of Every SoT File
Pattern 5 Entry Signature means Vela SoT entries use bullet, date, and indented context.
Pattern 6 Protected and Fluid Zones means `000.Index` declarations, block maps, lineage, and canonical entries are protected while living-record updates stay more fluid.
Pattern 7 Single Source Block Map means structural identity is declared once inside each SoT.
Pattern 8 Unified Compass means WHY and WHY NOT stay under `600`.
Pattern 9 Declaration Anchor means Subject Declaration remains in `000.Index`.
The Living Record inside `000.Index` is ordered `Inbox`, `Status`, `Open Questions`, `Next Actions`, then append-only `Decisions`.

## This Constitution Applies the Behavioral Patterns to Mutation and Growth
Pattern 10 Dual Archive means archived content belongs in both the original dimension's inactive area and `700.Archive`.
Pattern 11 Lightest Intervention means Vela should prefer flat, then fractal, then ref, then spawned SoT.
Pattern 12 Sovereign Spawn means child SoTs reset to their own `000–700` numbering while keeping lineage through parent and links.
Pattern 13 Extraction Before Deletion means no meaningful content is deleted without being extracted first.
Archive protocol means the entry moves from `Active` to `Inactive`, receives archived date and reason, and is also appended to `700.Archive`.

## This Constitution Applies the Operational Patterns to Governance and Runtime Behavior
Pattern 14 One Home Many Pointers means content lives once and is seen elsewhere through links or refs.
Pattern 15 Three-Hop Ceiling means the matrix should stay navigable from the cornerstone without depth sprawl.
Pattern 16 Frontmatter Contract means `sot-type`, `created`, `last-rewritten`, `parent`, `domain`, and `status` are required. `tags` remain supported but optional.
Pattern 17 SoT-Native Output means Vela agents should produce matrix-native structures rather than ad hoc prose dumps.
Pattern 18 Human Gate means identity-level or sovereign changes require explicit approval.
Pattern 19 Day Night Cycle means operational agents can work continuously, but governance still separates production, validation, maintenance, and improvement roles.

## This Constitution Applies the Three Hop Rule Through Explicit Dimension Hubs
Dimension hubs are the only ordinary SoTs that should attach directly to the cornerstone. Branch SoTs should prefer the relevant dimension hub or a governed local parent so the tree stays legible as Cornerstone → hub → parent → child.

## This Constitution Applies the Numbered Naming Scheme to Canonical Files
Canonical SoTs follow `{ID}.{Context}.{Subject}-SoT.md` for hubs and branch SoTs, with the cornerstone as the singular exception. Governed references use letter-suffixed IDs in the broader framework, while this repository currently keeps named governed refs under `knowledge/ARTIFACTS/refs/` until a fuller ref-ID scheme is adopted.

## This Constitution Defines the Vela Runtime Roles in Matrix Terms
The Router and Planner prepare pathing.
The Worker acts as a matrix-aware Scribe for draft production.
The Warden acts as the validator and rule-enforcer.
The Grower handles lightest-intervention evolution.
The broader improvement role still needs a clearer Dreamer analogue in the repo.

## This Constitution Commits the Repository to Mechanical Enforcement Rather Than Vague Alignment
The Python matrix validator and the Rust governance boundary should keep moving toward explicit enforcement of the Matrix framework so Vela does not merely talk about SoTs but actually behaves like a matrix-native system.
