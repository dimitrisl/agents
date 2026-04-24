with open("main.py", "r") as f:
    content = f.read()

# 1. Update session state initialization
old_session_state = """if "char_name" not in st.session_state:
    logger.debug("Initializing default session state variables.")
    st.session_state.char_name = "Eldred the Valiant"
    st.session_state.char_class = "Paladin"
    st.session_state.char_level = 5
    st.session_state.stats = {
        "STR": 18,
        "DEX": 12,
        "CON": 15,
        "INT": 10,
        "WIS": 14,
        "CHA": 16,
    }
    st.session_state.build_suggestion = "Click 'Generate New Build Suggestion' to get an AI recommendation based on your current stats!"
    st.session_state.encounter_result = ""
    st.session_state.campaign_notes = "The Party enters the lower levels. You need to prepare encounters for the Goblin warren."
    st.session_state.npc_result = ""
"""
new_session_state = """if "char_name" not in st.session_state:
    logger.debug("Initializing default session state variables.")
    st.session_state.char_name = "Eldred the Valiant"
    st.session_state.char_class = "Paladin"
    st.session_state.char_level = 5
    st.session_state.race = "Human"
    st.session_state.background = "Soldier"
    st.session_state.alignment = "Lawful Good"
    st.session_state.armor_class = 18
    st.session_state.hp_max = 44
    st.session_state.speed = 30
    st.session_state.proficiency_bonus = 3
    st.session_state.stats = {
        "STR": 18,
        "DEX": 12,
        "CON": 15,
        "INT": 10,
        "WIS": 14,
        "CHA": 16,
    }
    st.session_state.saving_throws = ["WIS", "CHA"]
    st.session_state.skills = {"Athletics": 7, "Intimidation": 6, "Persuasion": 6}
    st.session_state.weapons = [{"name": "Longsword", "attack_bonus": "+7", "damage": "1d8+4 slashing"}]
    st.session_state.equipment = ["Chain mail", "Shield", "Explorer's pack"]
    st.session_state.features_traits = [{"name": "Divine Smite", "description": "Expend a spell slot to deal radiant damage."}]
    st.session_state.spells = {"level_1": ["Bless", "Cure Wounds", "Shield of Faith"], "level_2": ["Find Steed", "Lesser Restoration"]}

    st.session_state.build_suggestion = "Click 'Generate New Build Suggestion' to get an AI recommendation based on your current stats!"
    st.session_state.encounter_result = ""
    st.session_state.campaign_notes = "The Party enters the lower levels. You need to prepare encounters for the Goblin warren."
    st.session_state.npc_result = ""
"""
content = content.replace(old_session_state, new_session_state)

# 2. Update Save Data
old_save = """        char_data = {
            "char_name": st.session_state.char_name,
            "char_class": st.session_state.char_class,
            "char_level": st.session_state.char_level,
            "stats": st.session_state.stats,
        }"""
new_save = """        char_data = {
            "char_name": st.session_state.char_name,
            "char_class": st.session_state.char_class,
            "char_level": st.session_state.char_level,
            "race": st.session_state.race,
            "background": st.session_state.background,
            "alignment": st.session_state.alignment,
            "armor_class": st.session_state.armor_class,
            "hp_max": st.session_state.hp_max,
            "speed": st.session_state.speed,
            "proficiency_bonus": st.session_state.proficiency_bonus,
            "stats": st.session_state.stats,
            "saving_throws": st.session_state.saving_throws,
            "skills": st.session_state.skills,
            "weapons": st.session_state.weapons,
            "equipment": st.session_state.equipment,
            "features_traits": st.session_state.features_traits,
            "spells": st.session_state.spells,
        }"""
content = content.replace(old_save, new_save)

# 3. Update Load Data
old_load = """                st.session_state.char_name = data.get("char_name", "Unknown")
                st.session_state.char_class = data.get("char_class", "Commoner")
                st.session_state.char_level = data.get("char_level", 1)
                if "stats" in data:
                    st.session_state.stats = data["stats"]"""
new_load = """                st.session_state.char_name = data.get("char_name", "Unknown")
                st.session_state.char_class = data.get("char_class", "Commoner")
                st.session_state.char_level = data.get("char_level", 1)
                st.session_state.race = data.get("race", "Unknown")
                st.session_state.background = data.get("background", "Unknown")
                st.session_state.alignment = data.get("alignment", "Unknown")
                st.session_state.armor_class = data.get("armor_class", 10)
                st.session_state.hp_max = data.get("hp_max", 10)
                st.session_state.speed = data.get("speed", 30)
                st.session_state.proficiency_bonus = data.get("proficiency_bonus", 2)
                st.session_state.saving_throws = data.get("saving_throws", [])
                st.session_state.skills = data.get("skills", {})
                st.session_state.weapons = data.get("weapons", [])
                st.session_state.equipment = data.get("equipment", [])
                st.session_state.features_traits = data.get("features_traits", [])
                st.session_state.spells = data.get("spells", {})
                if "stats" in data:
                    st.session_state.stats = data["stats"]"""
content = content.replace(old_load, new_load)


# 4. Overhaul Tab 1 (Active Character)
old_tab1 = """        edit_mode = st.toggle("✏️ Edit Character")

        if edit_mode:
            logger.debug("User entered Character Edit Mode.")
            st.markdown("### Edit Character Details")
            col_n, col_c, col_l = st.columns([2, 2, 1])
            st.session_state.char_name = col_n.text_input(
                "Name", st.session_state.char_name
            )
            st.session_state.char_class = col_c.text_input(
                "Class", st.session_state.char_class
            )
            st.session_state.char_level = col_l.number_input(
                "Level", min_value=1, max_value=20, value=st.session_state.char_level
            )

            st.markdown("#### Ability Scores")
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            st.session_state.stats["STR"] = c1.number_input(
                "STR", 1, 30, st.session_state.stats["STR"]
            )
            st.session_state.stats["DEX"] = c2.number_input(
                "DEX", 1, 30, st.session_state.stats["DEX"]
            )
            st.session_state.stats["CON"] = c3.number_input(
                "CON", 1, 30, st.session_state.stats["CON"]
            )
            st.session_state.stats["INT"] = c4.number_input(
                "INT", 1, 30, st.session_state.stats["INT"]
            )
            st.session_state.stats["WIS"] = c5.number_input(
                "WIS", 1, 30, st.session_state.stats["WIS"]
            )
            st.session_state.stats["CHA"] = c6.number_input(
                "CHA", 1, 30, st.session_state.stats["CHA"]
            )

        else:
            st.markdown(f"### Active Character: **{st.session_state.char_name}**")
            st.markdown("#### Ability Scores")
            c1, c2, c3, c4, c5, c6 = st.columns(6)

            def format_mod(score):
                mod = calculate_modifier(score)
                return f"+{mod}" if mod >= 0 else f"{mod}"

            c1.metric(
                "STR",
                st.session_state.stats["STR"],
                format_mod(st.session_state.stats["STR"]),
            )
            c2.metric(
                "DEX",
                st.session_state.stats["DEX"],
                format_mod(st.session_state.stats["DEX"]),
            )
            c3.metric(
                "CON",
                st.session_state.stats["CON"],
                format_mod(st.session_state.stats["CON"]),
            )
            c4.metric(
                "INT",
                st.session_state.stats["INT"],
                format_mod(st.session_state.stats["INT"]),
            )
            c5.metric(
                "WIS",
                st.session_state.stats["WIS"],
                format_mod(st.session_state.stats["WIS"]),
            )
            c6.metric(
                "CHA",
                st.session_state.stats["CHA"],
                format_mod(st.session_state.stats["CHA"]),
            )"""

new_tab1 = """        st.markdown(f"### Active Character: **{st.session_state.char_name}**")
        st.write(f"{st.session_state.race} | {st.session_state.background} | {st.session_state.alignment}")

        edit_mode = st.toggle("✏️ Edit Mode")

        char_tab1, char_tab2, char_tab3 = st.tabs(["📊 Core Stats & Skills", "⚔️ Combat & Inventory", "✨ Features & Spells"])

        with char_tab1:
            if edit_mode:
                c_n, c_c, c_l, c_r = st.columns(4)
                st.session_state.char_name = c_n.text_input("Name", st.session_state.char_name)
                st.session_state.char_class = c_c.text_input("Class", st.session_state.char_class)
                st.session_state.char_level = c_l.number_input("Level", 1, 20, st.session_state.char_level)
                st.session_state.race = c_r.text_input("Race", st.session_state.race)

                c_b, c_a, c_hp, c_ac = st.columns(4)
                st.session_state.background = c_b.text_input("Background", st.session_state.background)
                st.session_state.alignment = c_a.text_input("Alignment", st.session_state.alignment)
                st.session_state.hp_max = c_hp.number_input("Max HP", 1, 500, st.session_state.hp_max)
                st.session_state.armor_class = c_ac.number_input("Armor Class", 1, 50, st.session_state.armor_class)

                st.markdown("#### Ability Scores")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                st.session_state.stats["STR"] = c1.number_input("STR", 1, 30, st.session_state.stats["STR"])
                st.session_state.stats["DEX"] = c2.number_input("DEX", 1, 30, st.session_state.stats["DEX"])
                st.session_state.stats["CON"] = c3.number_input("CON", 1, 30, st.session_state.stats["CON"])
                st.session_state.stats["INT"] = c4.number_input("INT", 1, 30, st.session_state.stats["INT"])
                st.session_state.stats["WIS"] = c5.number_input("WIS", 1, 30, st.session_state.stats["WIS"])
                st.session_state.stats["CHA"] = c6.number_input("CHA", 1, 30, st.session_state.stats["CHA"])

                st.markdown("#### Skills & Saves")
                st.session_state.skills = st.data_editor(st.session_state.skills, num_rows="dynamic", key="edit_skills")
                st.write("Saving Throws:", st.session_state.saving_throws)

            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Max HP", st.session_state.hp_max)
                c2.metric("Armor Class", st.session_state.armor_class)
                c3.metric("Speed", f"{st.session_state.speed} ft")
                c4.metric("Proficiency", f"+{st.session_state.proficiency_bonus}")

                st.markdown("#### Ability Scores")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                def format_mod(score):
                    mod = calculate_modifier(score)
                    return f"+{mod}" if mod >= 0 else f"{mod}"
                c1.metric("STR", st.session_state.stats["STR"], format_mod(st.session_state.stats["STR"]))
                c2.metric("DEX", st.session_state.stats["DEX"], format_mod(st.session_state.stats["DEX"]))
                c3.metric("CON", st.session_state.stats["CON"], format_mod(st.session_state.stats["CON"]))
                c4.metric("INT", st.session_state.stats["INT"], format_mod(st.session_state.stats["INT"]))
                c5.metric("WIS", st.session_state.stats["WIS"], format_mod(st.session_state.stats["WIS"]))
                c6.metric("CHA", st.session_state.stats["CHA"], format_mod(st.session_state.stats["CHA"]))

                col_sk, col_sv = st.columns(2)
                with col_sk:
                    st.markdown("#### Skills")
                    for k, v in st.session_state.skills.items():
                        st.write(f"**{k}:** {v}")
                with col_sv:
                    st.markdown("#### Saving Throws")
                    st.write(", ".join(st.session_state.saving_throws))

        with char_tab2:
            st.markdown("#### Weapons")
            if edit_mode:
                st.session_state.weapons = st.data_editor(st.session_state.weapons, num_rows="dynamic", key="edit_weapons")
            else:
                for w in st.session_state.weapons:
                    st.write(f"🗡️ **{w.get('name', 'Unknown')}** | Atk: {w.get('attack_bonus', '+0')} | Dmg: {w.get('damage', '1d4')}")

            st.markdown("#### Equipment")
            if edit_mode:
                st.session_state.equipment = st.data_editor([{"item": e} for e in st.session_state.equipment], num_rows="dynamic", key="edit_equip")
                st.session_state.equipment = [i["item"] for i in st.session_state.equipment if "item" in i]
            else:
                st.write(", ".join(st.session_state.equipment))

        with char_tab3:
            st.markdown("#### Features & Traits")
            if edit_mode:
                st.session_state.features_traits = st.data_editor(st.session_state.features_traits, num_rows="dynamic", key="edit_features")
            else:
                for f in st.session_state.features_traits:
                    st.write(f"**{f.get('name', '')}:** {f.get('description', '')}")

            st.markdown("#### Spells")
            if edit_mode:
                import json
                spells_str = st.text_area("Spells (JSON format)", value=json.dumps(st.session_state.spells, indent=2), height=200)
                try:
                    st.session_state.spells = json.loads(spells_str)
                except:
                    st.error("Invalid JSON format for spells.")
            else:
                if not st.session_state.spells:
                    st.write("No spells known.")
                else:
                    for lvl, spell_list in st.session_state.spells.items():
                        st.write(f"**{lvl.title().replace('_', ' ')}:** {', '.join(spell_list)}")
"""

content = content.replace(old_tab1, new_tab1)

# 5. Overhaul AI Generator
old_ai_gen = """        concept = st.text_area(
            "Character Concept:",
            "A grumpy dwarven baker who uses a massive rolling pin as a weapon.",
        )

        if st.button("Generate Character", type="primary"):
            logger.info(f"User requested AI Character Forge with concept: {concept}")
            with st.spinner("Rolling stats and forging character..."):
                prompt = f\"\"\"
                Create a level 1 D&D 5e character based on this concept: "{concept}"
                You must assign them a balanced array of 6 ability scores that fit their class and race optimally.

                Output the character strictly as a JSON object with exactly the following schema:
                {{
                    "char_name": "Name of the character",
                    "char_class": "Class (e.g., Fighter, Wizard)",
                    "stats": {{
                        "STR": 15, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10
                    }}
                }}
                \"\"\"

                result = generate_ai_json(prompt)

                if result and "char_name" in result:
                    logger.info(
                        f"Successfully generated and parsed new character: {result.get('char_name')}"
                    )
                    st.session_state.char_name = result.get("char_name", "Unknown")
                    st.session_state.char_class = result.get("char_class", "Commoner")
                    st.session_state.char_level = 1

                    if "stats" in result:
                        st.session_state.stats = result["stats"]"""

new_ai_gen = """        concept = st.text_area(
            "Character Concept:",
            "A grumpy dwarven baker who uses a massive rolling pin as a weapon.",
        )
        target_level = st.number_input("Target Level", min_value=1, max_value=20, value=1)

        if st.button("Generate Character", type="primary"):
            logger.info(f"User requested AI Character Forge with concept: {concept} at level {target_level}")
            with st.spinner("Rolling stats and forging character..."):
                prompt = f\"\"\"
                Create a fully fleshed out level {target_level} D&D 5e character based on this concept: "{concept}"
                You must assign them a balanced array of 6 ability scores, calculate their HP, AC, Proficiency Bonus, and choose appropriate skills, weapons, equipment, features/traits, and spells (if applicable) for a level {target_level} character.

                Output the character strictly as a JSON object with exactly the following schema:
                {{
                    "char_name": "Name of the character",
                    "char_class": "Class (e.g., Fighter, Wizard)",
                    "char_level": {target_level},
                    "race": "Race",
                    "background": "Background",
                    "alignment": "Alignment",
                    "armor_class": 16,
                    "hp_max": 45,
                    "speed": 30,
                    "proficiency_bonus": 3,
                    "stats": {{
                        "STR": 15, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10
                    }},
                    "saving_throws": ["STR", "CON"],
                    "skills": {{"Athletics": 5, "Intimidation": 2}},
                    "weapons": [{{"name": "Warhammer", "attack_bonus": "+5", "damage": "1d8+3 bludgeoning"}}],
                    "equipment": ["Chain mail", "Backpack"],
                    "features_traits": [{{"name": "Action Surge", "description": "Push yourself..."}}],
                    "spells": {{"cantrips": ["Fire Bolt"], "level_1": ["Shield"]}}
                }}
                \"\"\"

                result = generate_ai_json(prompt)

                if result and "char_name" in result:
                    logger.info(
                        f"Successfully generated and parsed new character: {result.get('char_name')}"
                    )
                    st.session_state.char_name = result.get("char_name", "Unknown")
                    st.session_state.char_class = result.get("char_class", "Commoner")
                    st.session_state.char_level = result.get("char_level", target_level)
                    st.session_state.race = result.get("race", "Unknown")
                    st.session_state.background = result.get("background", "Unknown")
                    st.session_state.alignment = result.get("alignment", "Unknown")
                    st.session_state.armor_class = result.get("armor_class", 10)
                    st.session_state.hp_max = result.get("hp_max", 10)
                    st.session_state.speed = result.get("speed", 30)
                    st.session_state.proficiency_bonus = result.get("proficiency_bonus", 2)
                    st.session_state.saving_throws = result.get("saving_throws", [])
                    st.session_state.skills = result.get("skills", {})
                    st.session_state.weapons = result.get("weapons", [])
                    st.session_state.equipment = result.get("equipment", [])
                    st.session_state.features_traits = result.get("features_traits", [])
                    st.session_state.spells = result.get("spells", {})

                    if "stats" in result:
                        st.session_state.stats = result["stats"]"""
content = content.replace(old_ai_gen, new_ai_gen)

with open("main.py", "w") as f:
    f.write(content)
