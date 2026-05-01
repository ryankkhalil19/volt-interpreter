1v ===> [-32v+] ===> || current_number ;
(~)[15v] {
    current_number ===> (%) 3v ===> (=) 0v ===> [+8v-] ===> || is_fizz ;
    current_number ===> (%) 5v ===> (=) 0v ===> [+8v-] ===> || is_buzz ;
    _/_[is_fizz] {
        [^]: _/_[is_buzz] {
            [^]: "FizzBuzz" ===> (O) ===> _|_ ;
            [v]: "Fizz" ===> (O) ===> _|_ ;
        }
        [v]: _/_[is_buzz] {
            [^]: "Buzz" ===> (O) ===> _|_ ;
            [v]: current_number ===> (O) ===> || current_number ;
        }
    }
    current_number ===> (+) 1v ===> || current_number ;
    is_fizz ===> _|_ ;
    is_buzz ===> _|_ ;
}
current_number ===> _|_ ;
