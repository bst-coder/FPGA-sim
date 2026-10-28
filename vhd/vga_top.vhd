
-------------------------------------------------------------------------------
-- vga_top.vhd
-- Top-level for Terasic DE1 / Altera Cyclone II
--
-- KEY0       : active-low reset
-- KEY1       : hold to freeze animation
-- SW1..SW0   : display mode
-- SW4..SW2   : RGB color selection
-- SW5        : scrolling background enable
-- SW9..SW8   : animation speed
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;

entity vga_top is
  port (
    CLOCK_50 : in  std_logic;
    KEY      : in  std_logic_vector(3 downto 0);
    SW       : in  std_logic_vector(9 downto 0);
    LEDR     : out std_logic_vector(9 downto 0);

    VGA_R    : out std_logic_vector(3 downto 0);
    VGA_G    : out std_logic_vector(3 downto 0);
    VGA_B    : out std_logic_vector(3 downto 0);
    VGA_HS   : out std_logic;
    VGA_VS   : out std_logic
  );
end entity vga_top;

architecture rtl of vga_top is

  -- Two-stage synchronizers for asynchronous inputs
  signal key_meta : std_logic_vector(3 downto 0) := (others => '1');
  signal key_sync : std_logic_vector(3 downto 0) := (others => '1');

  signal sw_meta  : std_logic_vector(9 downto 0) := (others => '0');
  signal sw_sync  : std_logic_vector(9 downto 0) := (others => '0');

  signal reset_n : std_logic;
  signal freeze  : std_logic;

  signal rgb_r, rgb_g, rgb_b : std_logic_vector(3 downto 0);
  signal row, col            : std_logic_vector(9 downto 0);

  signal frame_tick : std_logic;
  signal video_on   : std_logic;

begin

  ---------------------------------------------------------------------------
  -- Synchronize switches and buttons to CLOCK_50.
  ---------------------------------------------------------------------------
  process (CLOCK_50)
  begin
    if rising_edge(CLOCK_50) then
      key_meta <= KEY;
      key_sync <= key_meta;

      sw_meta <= SW;
      sw_sync <= sw_meta;
    end if;
  end process;

  reset_n <= key_sync(0);
  freeze  <= not key_sync(1);

  LEDR <= sw_sync;

  ---------------------------------------------------------------------------
  -- Pattern generator
  ---------------------------------------------------------------------------
  u_pattern : entity work.vga_pattern
    port map (
      clock_50     => CLOCK_50,
      reset_n      => reset_n,
      frame_tick   => frame_tick,
      freeze       => freeze,
      mode         => sw_sync(1 downto 0),
      color_sel    => sw_sync(4 downto 2),
      speed        => sw_sync(9 downto 8),
      scroll_en    => sw_sync(5),
      pixel_row    => row,
      pixel_column => col,
      red          => rgb_r,
      green        => rgb_g,
      blue         => rgb_b
    );

  ---------------------------------------------------------------------------
  -- VGA timing and output stage
  ---------------------------------------------------------------------------
  u_sync : entity work.vga_sync
    generic map (
      CLK_DIV => 2
    )
    port map (
      clock_50       => CLOCK_50,
      reset_n        => reset_n,

      red            => rgb_r,
      green          => rgb_g,
      blue           => rgb_b,

      red_out        => VGA_R,
      green_out      => VGA_G,
      blue_out       => VGA_B,

      horiz_sync_out => VGA_HS,
      vert_sync_out  => VGA_VS,

      video_on       => video_on,
      frame_tick     => frame_tick,

      pixel_row      => row,
      pixel_column   => col
    );

end architecture rtl;
