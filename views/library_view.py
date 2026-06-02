import streamlit as st
from backend.repositories.rules_repository import RulesRepository
from backend.core.constants import EDITION_2014
from backend.utils.ui_utils import render_themed_markdown


def render_library_view():
    st.header("📚 Rules Library")
    st.markdown("Browse the available feats and classes.")

    edition = st.session_state.get("dnd_edition", EDITION_2014)
    repo = RulesRepository()

    tabs = st.tabs(
        [
            "📜 AI Rules Oracle",
            "⚖️ Rule Comparison",
            "✨ Spells",
            "🛡️ Feats",
            "🧙 Classes",
        ]
    )

    # AI Rules Oracle Tab
    with tabs[0]:
        st.subheader("📜 AI Rules Oracle")
        st.markdown(
            "Ask any question about D&D 5e/5.5e rules, features, spells, or mechanics. The Oracle will consult the archives and guide you."
        )

        rule_query = st.text_input(
            "Ask about a rule or feature:",
            placeholder="e.g. How does Sneak Attack work?",
            key="oracle_rule_query_input",
        )

        if st.button(
            "Query Oracle", key="oracle_rule_query_btn", type="primary", width="stretch"
        ):
            if rule_query:
                from backend.services.rules_service import query_rules

                with st.spinner("Consulting the archives..."):
                    answer = query_rules(rule_query, edition)
                    st.session_state.last_library_rule_answer = answer
            else:
                st.warning("Please enter a question.")

        if st.session_state.get("last_library_rule_answer"):
            st.markdown("---")
            answer = st.session_state.last_library_rule_answer
            if "⚠️" in answer or "❌" in answer:
                st.error(answer)
            else:
                render_themed_markdown(answer)

            if st.button("Clear Answer", key="clear_oracle_answer", width="stretch"):
                st.session_state.last_library_rule_answer = None
                st.rerun()

    # Rule Comparison Tab
    with tabs[1]:
        st.subheader("⚖️ 2014 vs. 2024 Comparison")
        st.markdown(
            "Compare the legacy 2014 rules with the new 2024 Revision (5.5e) mechanics."
        )

        compare_query = st.text_input(
            "Rule or Feat to compare:",
            placeholder="e.g. Great Weapon Master, Grappled condition, Surprise...",
            key="rule_compare_input",
        )

        if st.button(
            "Compare Rules", key="rule_compare_btn", type="primary", width="stretch"
        ):
            if compare_query:
                from backend.services.rules_service import compare_rules

                with st.spinner("Analyzing the evolution of rules..."):
                    comparison = compare_rules(compare_query)
                    st.session_state.last_rule_comparison = comparison
            else:
                st.warning("Please enter a rule to compare.")

        if st.session_state.get("last_rule_comparison"):
            st.markdown("---")
            render_themed_markdown(st.session_state.last_rule_comparison)
            if st.button("Clear Comparison", key="clear_compare_btn", width="stretch"):
                st.session_state.last_rule_comparison = None
                st.rerun()

    # Spells Tab
    with tabs[2]:
        st.subheader(f"Spells ({edition})")
        spells = repo.get_all_spells(edition)

        if not spells:
            st.info(
                "No spells found for this edition. Try running the import script first."
            )
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                search_query = st.text_input(
                    "Search Spells by Name", key="spell_search"
                )
            with col2:
                level_filter = st.selectbox(
                    "Level",
                    [
                        "All",
                        "Cantrip",
                        "1st Level",
                        "2nd Level",
                        "3rd Level",
                        "4th Level",
                        "5th Level",
                        "6th Level",
                        "7th Level",
                        "8th Level",
                        "9th Level",
                    ],
                    key="spell_level_filter",
                )
            with col3:
                school_filter = st.selectbox(
                    "School",
                    [
                        "All",
                        "Abjuration",
                        "Conjuration",
                        "Divination",
                        "Enchantment",
                        "Evocation",
                        "Illusion",
                        "Necromancy",
                        "Transmutation",
                    ],
                    key="spell_school_filter",
                )

            col4, col5, col6 = st.columns(3)
            with col4:
                class_filter = st.selectbox(
                    "Class Compatibility",
                    [
                        "All",
                        "Bard",
                        "Cleric",
                        "Druid",
                        "Paladin",
                        "Ranger",
                        "Sorcerer",
                        "Warlock",
                        "Wizard",
                    ],
                    key="spell_class_filter",
                )
            with col5:
                conc_filter = st.selectbox(
                    "Concentration", ["All", "Yes", "No"], key="spell_conc_filter"
                )
            with col6:
                ritual_filter = st.selectbox(
                    "Ritual", ["All", "Yes", "No"], key="spell_ritual_filter"
                )

            # Filtering logic
            filtered_spells = spells
            if search_query:
                filtered_spells = [
                    s
                    for s in filtered_spells
                    if search_query.lower() in s.get("name", "").lower()
                ]

            if level_filter != "All":
                level_val = (
                    0 if level_filter == "Cantrip" else int(level_filter.split()[0][0])
                )
                filtered_spells = [
                    s for s in filtered_spells if s.get("level") == level_val
                ]

            if school_filter != "All":
                filtered_spells = [
                    s
                    for s in filtered_spells
                    if s.get("school", "").lower() == school_filter.lower()
                ]

            if class_filter != "All":
                filtered_spells = [
                    s
                    for s in filtered_spells
                    if class_filter.lower() in [c.lower() for c in s.get("classes", [])]
                ]

            if conc_filter != "All":
                is_conc = conc_filter == "Yes"
                filtered_spells = [
                    s
                    for s in filtered_spells
                    if s.get("concentration", False) == is_conc
                ]

            if ritual_filter != "All":
                is_rit = ritual_filter == "Yes"
                filtered_spells = [
                    s for s in filtered_spells if s.get("ritual", False) == is_rit
                ]

            st.write(f"Showing **{len(filtered_spells)}** spells of {len(spells)}")

            # Display spells in expanders
            for spell in sorted(filtered_spells, key=lambda x: x.get("name", "")):
                # Construct suffix labels
                lvl = spell.get("level", 0)
                lvl_str = (
                    "Cantrip"
                    if lvl == 0
                    else f"{lvl}th-level"
                    if lvl not in [1, 2, 3]
                    else "1st-level"
                    if lvl == 1
                    else "2nd-level"
                    if lvl == 2
                    else "3rd-level"
                )
                school = spell.get("school", "Unknown").title()

                tags = []
                if spell.get("concentration"):
                    tags.append("⏱️ Concentration")
                if spell.get("ritual"):
                    tags.append("📜 Ritual")

                tags_str = f" ({', '.join(tags)})" if tags else ""
                label = f"{spell.get('name')} — {lvl_str} {school}{tags_str}"

                with st.expander(label):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(
                            f"**Casting Time:** {spell.get('castingTime', '1 action')}"
                        )
                        st.markdown(f"**Range:** {spell.get('range', 'Touch')}")
                        st.markdown(
                            f"**Duration:** {spell.get('duration', 'Instantaneous')}"
                        )
                    with c2:
                        comps = [c.upper() for c in spell.get("components", [])]
                        comps_str = ", ".join(comps) if comps else "None"
                        st.markdown(f"**Components:** {comps_str}")
                        if spell.get("material"):
                            st.markdown(f"**Materials:** *{spell.get('material')}*")
                        st.markdown(
                            f"**Classes:** {', '.join([c.title() for c in spell.get('classes', [])])}"
                        )

                    st.markdown("---")
                    st.markdown(spell.get("description", ""))
                    if spell.get("higherLevelSlot"):
                        st.markdown(
                            f"**At Higher Levels:** {spell.get('higherLevelSlot')}"
                        )

    # Feats Tab
    with tabs[3]:
        st.subheader(f"Feats ({edition})")
        feats = repo.get_all_feats(edition)

        if not feats:
            st.info("No feats found for this edition.")
        else:
            search_query = st.text_input("Search Feats", key="feat_search")
            if search_query:
                feats = repo.search_feats(search_query, edition)

            for feat in feats:
                with st.expander(feat.get("name", "Unknown Feat")):
                    st.markdown(f"**Category:** {feat.get('category', 'N/A')}")
                    st.markdown(feat.get("description", ""))

    # Classes Tab
    with tabs[4]:
        st.subheader(f"Classes ({edition})")
        classes = repo.get_available_classes(edition)

        if not classes:
            st.info("No classes found for this edition.")
        else:
            selected_class = st.selectbox("Select a Class", classes)
            if selected_class:
                class_data = repo.get_class_progression(selected_class, edition)
                if class_data:
                    st.markdown(f"### {class_data.get('class_name', selected_class)}")
                    st.markdown(
                        f"**Hit Die:** {class_data.get('hit_die', 'N/A')} | **Primary Ability:** {', '.join(class_data.get('primary_ability', []))}"
                    )

                    st.markdown("#### Class Progression")
                    progression = class_data.get("progression", {})
                    for level in sorted([int(k) for k in progression.keys()]):
                        level_data = progression[str(level)]
                        features = level_data.get("features", [])
                        if features:
                            st.markdown(
                                f"**Level {level}** (PB: +{level_data.get('proficiency_bonus', 2)})"
                            )
                            for feature in features:
                                st.markdown(
                                    f"- **{feature.get('name', 'Unknown')}:** {feature.get('description', '')}"
                                )
                            st.markdown("---")
