import ../src/mettascope/[common, configs]

block test_load_config:
  let config = loadConfig()
  doAssert config.windowWidth > 0
  doAssert config.windowHeight > 0

block test_deserialize_monologue_panel:
  let referenceArea = Area(panels: @[Panel(name: "Score"), Panel(name: "Monologue")])
  let config = AreaLayoutConfig(panelNames: @["Monologue", "Score"])
  let area = deserializeArea(config, referenceArea)

  doAssert area.panels.len == 2
  doAssert area.panels[0].name == "Monologue"
  doAssert area.panels[1].name == "Score"
