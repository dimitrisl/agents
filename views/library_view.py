import streamlit as st
from backend.repositories.rules_repository import RulesRepository
from backend.core.constants import EDITION_2014


def render_library_view():
    st.header("📚 Rules Library")
    st.markdown("Browse the available feats and classes.")

    edition = st.session_state.get("dnd_edition", EDITION_2014)
    repo = RulesRepository()

    tabs = st.tabs(["Feats", "Classes"])

    # Feats Tab
    with tabs[0]:
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
    with tabs[1]:
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
