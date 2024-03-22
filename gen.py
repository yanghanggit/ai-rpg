
def main() -> None:


    try:

        pass

    except Exception as e:
        #logger.exception(e)
        return        

    

    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            break

        

###############################################################################################################################################


if __name__ == "__main__":
    main()