# Sensor Mounting

The EVAL-ADXL355-PMDZ should be treated as a precision remote sensor head.

## Mounting goals

- Rigid coupling to the building surface or test article.
- Minimal rocking or cable-induced motion.
- Repeatable axis orientation.
- Mechanical protection without stressing the PCB.

## Prototype mounting

For early tests, mount the PMOD board to a small aluminum block or puck using nylon hardware or a thin insulated spacer if there is any risk of shorting pads to the block. Keep the board flat and avoid bending it.

The puck can be attached to the structure with:

- Wax or removable adhesive for temporary low-force lab measurements.
- Screws or clamps for repeatable tests.
- Epoxy only when permanent mounting is acceptable.

## Cable handling

Strain-relieve the cable near the sensor head so cable movement does not shake the board. Avoid pulling the PMOD connector sideways.

## Orientation record

Record axis orientation in field notes and reports. A simple convention is:

- X: horizontal along the long axis of the block.
- Y: horizontal transverse.
- Z: vertical.

Confirm the actual board axes against the ADXL355 package and board markings before relying on direction-sensitive data.

## Calibration limits

Static +/-1 g calibration can improve DC offset and scale estimates. It does not provide traceable dynamic calibration, frequency-response calibration, or mounting transmissibility validation.
