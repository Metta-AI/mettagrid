import ../src/vibescope/configs

echo "Loading config..."
let config = loadConfig()

echo ""
echo "Current config values:"
echo "  windowWidth: " & $config.windowWidth
echo "  windowHeight: " & $config.windowHeight
echo "  panelLayout layout: " & $config.panelLayout.layout
echo "  panelLayout split: " & $config.panelLayout.split
echo "  panelLayout areas: " & $config.panelLayout.areas.len
echo "  panelLayout panelNames: " & $config.panelLayout.panelNames.len

echo ""
echo "Config system test completed successfully!"
