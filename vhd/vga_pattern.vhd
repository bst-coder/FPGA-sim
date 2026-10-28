
-------------------------------------------------------------------------------
-- vga_pattern.vhd
-- Four VGA display modes for 640x480 @ 60 Hz
--
-- mode = "00" : solid color
-- mode = "01" : 8 horizontal color bands
-- mode = "10" : 8 vertical color bars
-- mode = "11" : 64x64 animated square with optional scrolling background
--
-- color_sel(2 downto 0) = R, G, B
-- speed = 00, 01, 10, 11 -> 1, 2, 3, 4 pixels/frame
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity vga_pattern is
  port (
    clock_50     : in  std_logic;
    reset_n      : in  std_logic;
    frame_tick   : in  std_logic;
    freeze       : in  std_logic;
    mode         : in  std_logic_vector(1 downto 0);
    color_sel    : in  std_logic_vector(2 downto 0);
    speed        : in  std_logic_vector(1 downto 0);
    scroll_en    : in  std_logic;
    pixel_row    : in  std_logic_vector(9 downto 0);
    pixel_column : in  std_logic_vector(9 downto 0);
    red          : out std_logic_vector(3 downto 0);
    green        : out std_logic_vector(3 downto 0);
    blue         : out std_logic_vector(3 downto 0)
  );
end entity vga_pattern;

architecture rtl of vga_pattern is

  constant SQ : integer := 64;

  signal sq_x   : integer range 0 to 576 := 100;
  signal sq_y   : integer range 0 to 416 := 60;
  signal dx_pos : std_logic := '1';
  signal dy_pos : std_logic := '1';

  signal scroll : integer range 0 to 639 := 0;
  signal step   : integer range 1 to 4;

  signal rgb : std_logic_vector(2 downto 0);

  -- Color order: white, yellow, cyan, green,
  --              magenta, red, blue, black.
  function bar_color(idx : integer) return std_logic_vector is
  begin
    case idx is
      when 0      => return "111";
      when 1      => return "110";
      when 2      => return "011";
      when 3      => return "010";
      when 4      => return "101";
      when 5      => return "100";
      when 6      => return "001";
      when others => return "000";
    end case;
  end function;

  function band80(v : integer) return integer is
  begin
    return v / 80;
  end function;

  function band60(v : integer) return integer is
  begin
    return v / 60;
  end function;

begin

  step <= to_integer(unsigned(speed)) + 1;

  ---------------------------------------------------------------------------
  -- Update animation once per frame.
  ---------------------------------------------------------------------------
  process (clock_50)
  begin
    if rising_edge(clock_50) then
      if reset_n = '0' then
        sq_x   <= 100;
        sq_y   <= 60;
        dx_pos <= '1';
        dy_pos <= '1';
        scroll <= 0;

      elsif frame_tick = '1' and freeze = '0' then

        -- Horizontal motion and bounce
        if dx_pos = '1' then
          if sq_x + step >= 576 then
            sq_x   <= 576;
            dx_pos <= '0';
          else
            sq_x <= sq_x + step;
          end if;
        else
          if sq_x <= step then
            sq_x   <= 0;
            dx_pos <= '1';
          else
            sq_x <= sq_x - step;
          end if;
        end if;

        -- Vertical motion and bounce
        if dy_pos = '1' then
          if sq_y + step >= 416 then
            sq_y   <= 416;
            dy_pos <= '0';
          else
            sq_y <= sq_y + step;
          end if;
        else
          if sq_y <= step then
            sq_y   <= 0;
            dy_pos <= '1';
          else
            sq_y <= sq_y - step;
          end if;
        end if;

        -- Scrolling background, modulo 640
        if scroll + step >= 640 then
          scroll <= scroll + step - 640;
        else
          scroll <= scroll + step;
        end if;

      end if;
    end if;
  end process;

  ---------------------------------------------------------------------------
  -- Combinational color generation.
  ---------------------------------------------------------------------------
  process (mode, color_sel, scroll_en, pixel_row, pixel_column,
           sq_x, sq_y, scroll)
    variable c   : integer;
    variable r   : integer;
    variable s   : integer;
    variable bg  : std_logic_vector(2 downto 0);
    variable sqc : std_logic_vector(2 downto 0);
  begin
    c := to_integer(unsigned(pixel_column));
    r := to_integer(unsigned(pixel_row));

    -- Default: black, including VGA blanking coordinates.
    rgb <= "000";

    if c < 640 and r < 480 then
      case mode is

        when "00" =>
          rgb <= color_sel;

        when "01" =>
          rgb <= bar_color(band60(r));

        when "10" =>
          rgb <= bar_color(band80(c));

        when others =>
          -- Background
          if scroll_en = '1' then
            s := c + scroll;
            if s >= 640 then
              s := s - 640;
            end if;
            bg := bar_color(band80(s));
          else
            bg := "000";
          end if;

          -- White square when color_sel = black
          if color_sel = "000" then
            sqc := "111";
          else
            sqc := color_sel;
          end if;

          -- Square area
          if c >= sq_x and c < sq_x + SQ and
             r >= sq_y and r < sq_y + SQ then
            if scroll_en = '1' then
              rgb <= not bg;
            else
              rgb <= sqc;
            end if;
          else
            rgb <= bg;
          end if;

      end case;
    end if;
  end process;

  -- Expand each RGB bit to 4 bits for the DE1 VGA output.
  red   <= (others => rgb(2));
  green <= (others => rgb(1));
  blue  <= (others => rgb(0));

end architecture rtl;
