"admin" ===> [+40v-] ===> || username ;
"password123" ===> [+96v-] ===> || password ;
username ===> (=) "admin" ===> [+8v-] ===> || is_valid_user ;
password ===> (=) "password123" ===> [+8v-] ===> || is_valid_password ;
_/_[is_valid_user] {
    [^]: _/_[is_valid_password] {
        [^]: "Access Granted" ===> (O) ===> _|_ ;
        [v]: "Access Denied: Bad Password" ===> (O) ===> _|_ ;
    }
    [v]: "Access Denied: Unknown User" ===> (O) ===> _|_ ;
}
username ===> _|_ ;
password ===> _|_ ;
is_valid_user ===> _|_ ;
is_valid_password ===> _|_ ;
