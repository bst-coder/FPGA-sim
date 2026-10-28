
-------------------------------------------------------------------------------
-- vga_sync.vhd
-- VGA 640x480 @ 60 Hz
-- Input clock: 50 MHz
-- Pixel enable: 25 MHz when CLK_DIV = 2
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity vga_sync is
  generic (
    CLK_DIV : positive := 2
  );
  port (
    clock_50       : in  std_logic;
    reset_n        : in  std_logic;

    red            : in  std_logic_vector(3 downto 0);
    green          : in  std_logic_vector(3 downto 0);
    blue           : in  std_logic_vector(3 downto 0);

    red_out        : out std_logic_vector(3 downto 0);
    green_out      : out std_logic_vector(3 downto 0);
    blue_out       : out std_logic_vector(3 downto 0);

    horiz_sync_out : out std_logic;
    vert_sync_out  : out std_logic;

    video_on       : out std_logic;
    frame_tick     : out std_logic;

    pixel_row      : out std_logic_vector(9 downto 0);
    pixel_column   : out std_logic_vector(9 downto 0)
  );
end entity vga_sync;

architecture rtl of vga_sync is

  constant H_VISIBLE : natural := 640;
  constant H_FP      : natural := 16;
  constant H_SYNC    : natural := 96;
  constant H_BP      : natural := 48;
  constant H_TOTAL   : natural := 800;

  constant V_VISIBLE : natural := 480;
  constant V_FP      : natural := 10;
  constant V_SYNC    : natural := 2;
  constant V_BP      : natural := 33;
  constant V_TOTAL   : natural := 525;

  signal clk_cnt  : natural range 0 to CLK_DIV - 1 := 0;
  signal h_count  : unsigned(9 downto 0) := (others => '0');
  signal v_count  : unsigned(9 downto 0) := (others => '0');

  signal video_on_i : std_logic;
  signal hs_i       : std_logic;
  signal vs_i       : std_logic;

begin

  -- Timing decode
  video_on_i <= '1'
    when (h_count < H_VISIBLE and v_count < V_VISIBLE)
    else '0';

  -- Active-low horizontal sync
  hs_i <= '0'
    when (h_count >= H_VISIBLE + H_FP and
          h_count <  H_VISIBLE + H_FP + H_SYNC)
    else '1';

  -- Active-low vertical sync
  vs_i <= '0'
    when (v_count >= V_VISIBLE + V_FP and
          v_count <  V_VISIBLE + V_FP + V_SYNC)
    else '1';

  video_on     <= video_on_i;
  pixel_column <= std_logic_vector(h_count);
  pixel_row    <= std_logic_vector(v_count);

  process (clock_50)
  begin
    if rising_edge(clock_50) then
      if reset_n = '0' then
        clk_cnt        <= 0;
        h_count        <= (others => '0');
        v_count        <= (others => '0');

        red_out        <= (others => '0');
        green_out      <= (others => '0');
        blue_out       <= (others => '0');

        horiz_sync_out <= '1';
        vert_sync_out  <= '1';
        frame_tick     <= '0';

      else
        frame_tick <= '0';

        -- Advance the VGA timing once every CLK_DIV clocks.
        if clk_cnt = CLK_DIV - 1 then
          clk_cnt <= 0;

          -- Register RGB and sync from the current pixel coordinates.
          if video_on_i = '1' then
            red_out   <= red;
            green_out <= green;
            blue_out  <= blue;
          else
            red_out   <= (others => '0');
            green_out <= (others => '0');
            blue_out  <= (others => '0');
          end if;

          horiz_sync_out <= hs_i;
          vert_sync_out  <= vs_i;

          -- One-clock pulse at the start of vertical blanking.
          if h_count = 0 and v_count = V_VISIBLE then
            frame_tick <= '1';
          end if;

          -- Horizontal and vertical counters
          if h_count = H_TOTAL - 1 then
            h_count <= (others => '0');

            if v_count = V_TOTAL - 1 then
              v_count <= (others => '0');
            else
              v_count <= v_count + 1;
            end if;
          else
            h_count <= h_count + 1;
          end if;

        else
          clk_cnt <= clk_cnt + 1;
        end if;
      end if;
    end if;
  end process;

end architecture rtl;
