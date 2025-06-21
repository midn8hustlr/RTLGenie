
module RefModule (
  input a,
  input b,
  input c,
  input d,
  output out_sop,
  output out_pos
);

  assign out_sop = c&d | ~a&~b&c;
  assign out_pos = (~a & ~b & c) | (b & c & d) | (a & c & d);

endmodule

