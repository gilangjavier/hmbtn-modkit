-- Runs in PCSX-Redux (-cli -dofile): watches the autotest mod's hm_test record and
-- reports it; hm.py test fills in the @...@ values.
local ffi = require('ffi')
local HM_TEST = @HM_TEST@
local SHOT_DIR = [[@SHOT_DIR@]]
local SCHEDULE = { @SCHEDULE@ }   -- { vsync, button to tap (0 = stop) }
local END = @END@
local LOG = [[@LOG@]]

-- Redux's safe mode (-cli) has no io library: Support.File writes the report.
local logfile = Support.File.open(LOG, 'TRUNCATE')
local function say(text)
    logfile:write(text .. string.char(10))
end

local mem = PCSX.getMemPtr()
local function u32(a) return ffi.cast('uint32_t*', mem + bit.band(a, 0x1fffff))[0] end
local function s32(a) return ffi.cast('int32_t*', mem + bit.band(a, 0x1fffff))[0] end
local function w32(a, v) ffi.cast('uint32_t*', mem + bit.band(a, 0x1fffff))[0] = v end

local function report(vsync)
    say(string.format('vsync=%d magic=%08x frames=%d scenes=%d last_scene=%d minutes=%d days=%d gold=%d pc=%08x',
        vsync, u32(HM_TEST), u32(HM_TEST + 4), u32(HM_TEST + 8), s32(HM_TEST + 12),
        u32(HM_TEST + 16), u32(HM_TEST + 20), s32(HM_TEST + 24), PCSX.getRegisters().pc))
end

local function shot(name)
    local ok, err = pcall(function()
        local ss = PCSX.GPU.takeScreenShot()
        local f = Support.File.open(SHOT_DIR .. '/' .. name .. '.raw', 'TRUNCATE')
        f:write(ss.data)
        f:close()
        say(string.format('shot %s %dx%d bpp=%d', name, tonumber(ss.width), tonumber(ss.height), tonumber(ss.bpp)))
    end)
    if not ok then say('shot failed: ' .. tostring(err)) end
end

local vsync = 0
local step = 1
hm_listener = PCSX.Events.createEventListener('GPU::Vsync', function()
    vsync = vsync + 1
    while SCHEDULE[step] and SCHEDULE[step][1] <= vsync do
        w32(HM_TEST + 28, SCHEDULE[step][2])
        say(string.format('vsync=%d autopilot=%04x', vsync, SCHEDULE[step][2]))
        shot(string.format('v%05d', vsync))
        step = step + 1
    end
    if vsync % 600 == 0 then report(vsync) end
    if vsync >= END then
        report(vsync)
        shot('final')
        logfile:close()
        PCSX.quit(0)
    end
end)
