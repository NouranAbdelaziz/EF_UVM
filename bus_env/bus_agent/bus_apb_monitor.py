from uvm.macros import uvm_component_utils, uvm_fatal, uvm_info, uvm_error
from uvm.comps.uvm_monitor import UVMMonitor
from uvm.tlm1.uvm_analysis_port import UVMAnalysisPort
from uvm.base.uvm_config_db import UVMConfigDb
from cocotb.triggers import Timer, RisingEdge, FallingEdge
from EF_UVM.bus_env.bus_item import bus_item
from uvm.base.uvm_object_globals import UVM_HIGH, UVM_LOW
import cocotb

class bus_apb_monitor(UVMMonitor):
    def __init__(self, name="bus_apb_monitor", parent=None):
        super().__init__(name, parent)
        self.monitor_port = UVMAnalysisPort("monitor_port", self)
        self.tag = name

    def build_phase(self, phase):
        super().build_phase(phase)
        arr = []
        if (not UVMConfigDb.get(self, "", "bus_if", arr)):
            uvm_fatal(self.tag, "No interface specified for self driver instance")
        else:
            self.sigs = arr[0]
        regs_arr = []
        if (not UVMConfigDb.get(self, "", "bus_regs", regs_arr)):
            uvm_fatal(self.tag, "No json file wrapper regs")
        else:
            self.regs = regs_arr[0]

    async def run_phase(self, phase):
        await cocotb.start(self.watch_reset())
        while True:
            tr = None
            # wait for a transaction
            while True:
                await self.sample_delay()
                if self.sigs.PSEL.value.binstr == "1" and self.sigs.PENABLE.value.binstr == "0":
                    break
            tr = bus_item.type_id.create("tr", self)
            tr.kind = bus_item.WRITE if self.sigs.PWRITE.value == 1 else bus_item.READ
            tr.addr = self.sigs.PADDR.value.integer
            await self.sample_delay()
            if self.sigs.PENABLE.value.binstr != "1":
                uvm_error(self.tag, f"APB protocol violation: SETUP cycle not followed by ENABLE cycle PENABLE={self.sigs.PENABLE.value.binstr}")
            if tr.kind == bus_item.WRITE:
                tr.data = self.sigs.PWDATA.value.integer
            else:
                try:
                    tr.data = self.sigs.PRDATA.value.integer
                except ValueError:
                    uvm_error(self.tag, f"PRDATA is not an integer {self.sigs.PRDATA.value.binstr}")
                    tr.data = self.sigs.PRDATA.value.binstr
            self.monitor_port.write(tr)
            # update reg value #TODO: move this to the ref_model later
            # self.regs.write_reg_value(tr.addr, tr.data)
            uvm_info(self.tag, "sampled APB transaction: " + tr.convert2string(), UVM_HIGH)

    async def watch_reset(self):
        while True:
            await FallingEdge(self.sigs.PRESETn)
            # send reset tr 
            tr = bus_item.type_id.create("tr", self)
            tr.reset = 1
            tr.kind = bus_item.READ
            tr.addr = 0
            self.monitor_port.write(tr)
            uvm_info(self.tag, "sampled reset transaction: " + tr.convert2string(), UVM_HIGH)

    async def sample_delay(self):
        await RisingEdge(self.sigs.PCLK)
        # await Timer(1, "NS")


uvm_component_utils(bus_apb_monitor)
