## Interconnect
* Clock system
    * [x] Single external clock
    * [x] Single clock generator
    * [ ] Multiple clock sources
* Reset system
    * [x] Single external reset
    * [ ] Single reset generator
    * [ ] Multiple reset sources
* Interrupts
    * [x] Complete pattern
    * [ ] Sparse pattern
* AXI Bus
    * [x] Single master
    * [x] Multiple masters
    * [ ] Non-complete interconnects
* [ ] AXI Stream

## Data lines
* [ ] Basic:
        - Connect all drivers to input pins. Creating extra outputs as needed
        - Drive all inputs from outputs, reusing if needed.
* [ ] Aggregator: If more outputs than inputs, support adding reduction functions

## IP
* Processing system
    * [x] Basic Microblaze
    * [ ] Configurations
* [x] GPIO
* [x] UART
* [ ] DMA

## Other
* [x] Multiple IP instances