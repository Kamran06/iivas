# IIVAS — Academic Discussion (Section 12)

*Graduate-level discussion situating the IIVAS project within corporate-
governance and institutional-investment scholarship.*

## Stewardship theory

Stewardship theory holds that institutional owners have a fiduciary
responsibility to monitor and engage with the companies they hold on behalf of
beneficiaries. For index funds this responsibility is acute and structurally
peculiar: because a passive fund must hold every constituent of its benchmark,
it cannot discipline a poorly governed company by selling. In Hirschman's
(1970) terms, *exit* is foreclosed and *voice* becomes the dominant channel.
Proxy voting is the most visible, auditable form of that voice, which is
precisely why the SEC mandates its disclosure on Form N-PX. IIVAS is, at root,
a measurement instrument for stewardship-as-voice: it quantifies how a manager
exercises the voice channel it is structurally compelled to rely on.

A central debate in the stewardship literature is whether the Big Three engage
in genuine monitoring or in low-cost, default-deferential voting. Critics
(Bebchuk & Hirst, 2019) argue that passive managers have weak incentives to
invest in costly stewardship because the benefits are diffused across the whole
index while the costs are borne by the manager; this predicts high
management-alignment scores. Defenders point to growing dissent on governance
and ESG items and to private engagement that voting records do not capture.
IIVAS speaks to the first prediction directly (are scores high and clustered?)
and is explicit that it cannot observe the second (private engagement is a
known blind spot, discussed in `PROJECT_EVALUATION.md`).

## Agency theory

The Jensen & Meckling (1976) agency framework frames the firm as a nexus of
contracts in which managers (agents) may pursue private benefits at the expense
of shareholders (principals). Proxy voting is one of the principal's primary
control mechanisms over the agent. Each IIVAS sub-score maps onto a distinct
agency conflict: the **governance** sub-score captures monitoring of the board,
the body charged with constraining managerial discretion; the **compensation**
sub-score captures the pay-setting conflict, the textbook locus of agency cost;
and the **ESG** sub-score captures contested questions about whether the firm
should internalise externalities, where principal preferences themselves
diverge. A manager that mechanically supports management across all three may
be under-supplying the monitoring that agency theory says principals require, a
"second-order" agency problem in which the monitor (the asset manager) is
itself an imperfect agent of the ultimate beneficiaries.

## Corporate governance

The project contributes to the empirical governance literature on the *content*
of institutional voting. A long line of work (e.g., Appel, Gormley & Keim,
2016) shows that the rise of passive ownership is associated with measurable
governance changes, more independent directors, fewer takeover defences,
suggesting passive owners are "passive investors, not passive owners." IIVAS
operationalises that distinction at the manager level and along governance
sub-dimensions, allowing a reader to ask not just *whether* a manager supports
management but *where* it chooses to dissent. The sector and size cuts (RQ4–5)
connect to the governance literature on how monitoring intensity varies with
firm visibility and ownership stakes.

## ESG investing

The ESG sub-score sits inside the most contested area of contemporary
governance: whether and how fiduciaries should weigh environmental and social
considerations. The 2024 modernization of Form N-PX, which standardised
categories and made filings machine-readable, was motivated precisely by
demand for transparency into how managers vote on ESG and say-on-pay items.
IIVAS is careful to separate two ESG constructs that are easily conflated:
support for *management* on an ESG matter, versus support for an ESG
*shareholder proposal* (which usually means voting against management). The
project measures both and flags the distinction, contributing methodological
clarity to a literature where "ESG support" is often reported ambiguously.

## Institutional ownership

Finally, the work connects to the macro literature on ownership concentration.
The Big Three's combined voting power has prompted concerns ranging from common
ownership effects on competition to the legitimacy of a small number of
unelected asset managers exercising outsized influence over corporate America.
By producing a transparent, reproducible, manager-level scorecard from public
data, IIVAS offers a small piece of the accountability infrastructure that this
concentration arguably requires.

## Contribution to the literature

The contribution is threefold. **Methodological:** a transparent, replicable
composite (with documented weights and graceful degradation) that others can
recompute and critique, in contrast to proprietary stewardship ratings.
**Empirical:** a structured panel of Big-Three voting decomposed by governance,
compensation, and ESG, enabling cross-manager, cross-sector, cross-size, and
longitudinal comparison. **Pedagogical/infrastructural:** an end-to-end open
pipeline from EDGAR to dashboard that lowers the barrier for future researchers
to extend the analysis to more filers and more years. The project is framed as
descriptive and predictive; it deliberately stops short of causal claims about
*why* managers vote as they do, leaving that to designs with exogenous
variation.

## References
- Appel, I., Gormley, T. A., & Keim, D. B. (2016). Passive investors, not passive owners. *Journal of Financial Economics*, 121(1).
- Bebchuk, L. A., & Hirst, S. (2019). Index funds and the future of corporate governance. *Columbia Law Review*, 119(8).
- Hirschman, A. O. (1970). *Exit, Voice, and Loyalty.* Harvard University Press.
- Jensen, M. C., & Meckling, W. H. (1976). Theory of the firm: managerial behavior, agency costs and ownership structure. *Journal of Financial Economics*, 3(4).
- Fichtner, J., Heemskerk, E. M., & Garcia-Bernardo, J. (2017). Hidden power of the Big Three. *Business and Politics*, 19(2).
