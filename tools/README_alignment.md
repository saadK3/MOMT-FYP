# Interactive Alignment Tool

## Quick Start

```bash
# From project root
python tools/interactive_alignment.py
```

## What It Does

Opens an interactive window with:

- Satellite image overlay on vehicle trajectories
- Sliders to adjust alignment:
  - **X Offset**: Move image left/right
  - **Y Offset**: Move image up/down
  - **Scale**: Zoom image in/out
  - **Rotation**: Rotate image (±45°)
  - **Opacity**: Transparency (0=invisible, 1=opaque)
- **Save Config** button to save final parameters

## How to Use

1. **Run the script** - A window opens showing satellite image + red trajectory dots
2. **Adjust sliders** - Move them until red dots align with roads
3. **Fine-tune** - Use small adjustments for precision
4. **Save** - Click "Save Config" button when satisfied
5. **Close window** - Configuration is saved to `visualization/alignment_config.json`

## Tips

- Start with **Opacity** at 0.5-0.6 to see both image and trajectories
- Use **X/Y Offset** for coarse positioning
- Use **Scale** if roads appear too wide/narrow
- Use **Rotation** if roads are at an angle
- Increase **Opacity** to 0.7-0.8 for final verification

## Output

Creates: `visualization/alignment_config.json`

This file contains all alignment parameters for the frontend visualization.

## Troubleshooting

**Image not loading:**

- Ensure `assets/GPS_intersection.png` exists
- Check image is not corrupted

**Sliders not responding:**

- Close and reopen the tool
- Check console for errors

**Alignment looks wrong:**

- Try different rotation angles
- Adjust scale (image might be wrong size)
- Verify you're looking at the correct intersection
